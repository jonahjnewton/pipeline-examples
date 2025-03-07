def export_usd_animcache(export_node, filepath, start_frame, end_frame, frame_stride, rig='', lookfile_uri='', publish_path='', skelRoot = '', skelOnly=False, frameHold=0):
    """
    Exports animation to USD, either as a deformed geo cache with surfacing URIs, or as a skeleton with rig URI.

    :param export_node:     The node to export to USD.
    :param filepath:        The path to exprot the USD file.
    :param start_frame:     The start frame to export the animation at.
    :param end_frame:       The end frame to export the animation at.
    :param frame_stride:    The frame stride to export the animation at.
    :param rig:             The filepath to the rig Maya Binary.
    :param lookfile_uri:    The URI for the asset's material lookfile. (Used in lighting for cryptomatte generation)
    :param publish_path:    The path to USD file will be published to. If this is set, publish-time USD manip[ulation will be done.
    :param skelRoot:        The root of the skeleton to export. If this is set, the skeleton will be included in the export.
    :param skelOnly:        If True, only the skeleton will be exported. If False, the deformed mesh will be exported.
    :param frameHold:       Number of frames to hold each frame for. 0 means no frame hold. A variant will be created for each frame hold combination.
    :return:
    """
    
    print("Node to export: " + export_node)
    try:
        properties = [("rig", rig), ("lookfileUri", lookfile_uri)]
        create_usd_user_properties(export_node, properties)
        
        if skelRoot:
            cmds.select(skelRoot, r=True)
            if not skelOnly:
                usdTypeName = cmds.addAttr(dt="string", ln='USD_typeName')
                cmds.setAttr(skelRoot + '.USD_typeName', 'SkelRoot', type="string")
            skelRoot_node_id = cmds.ls(skelRoot, uuid=True)[0]
            skelRoot_node_short = skelRoot.split("|")[-1]

        export_node_id = cmds.ls(export_node, uuid=True)[0]
        export_node_short = export_node.split("|")[-1]

        # Precheck to force anim cache to reparent root node of reference
        if cmds.referenceQuery(export_node, isNodeReferenced=True):
            reparent_node = utils.get_root_reference_node(export_node)
            print("Node " + [n for n in cmds.ls(export_node_id, long=True) if export_node_short in n][0] + " was reference node, switching node to reference root: " + str(reparent_node))
        else:
            reparent_node = export_node

        with utils.maya_keep_parent(reparent_node) as rp_node:
            cmds.parent(rp_node, world=True)
            reparented_export_node = [n for n in cmds.ls(export_node_id, long=True) if export_node_short in n][0]
            print("Trying to export: " + reparented_export_node)
            cmds.select(reparented_export_node, r=True)

            if skelRoot:
                #cmds.select(cmds.listRelatives(reparented_export_node, p=True)[0], r=True)
                reparented_skelRoot = [n for n in cmds.ls(skelRoot_node_id, long=True) if skelRoot_node_short in n][0]

                if skelOnly:
                    cmds.select(reparented_skelRoot)
                else:
                    cmds.select(reparented_skelRoot, add=True)

            options = ['shadingMode=none',
                    'exportRefsAsInstanceable=0',
                    'exportUVs=1',
                    'exportMaterialCollections=0',
                    'materialCollectionsPath=/Collections',
                    'exportColorSets=1',
                    'renderableOnly=0',
                    'mergeTransformAndShape=1',
                    'exportInstances=1',
                    'defaultMeshScheme=catmullClark',
                    'exportVisibility=1',
                    'animation=1',
                    'stripNamespaces=1',
                    'startTime=%d' % start_frame,
                    'endTime=%d' % end_frame,
                    'frameStride=%s' % frame_stride]
            
            if skelRoot and not skelOnly:
                options += ['exportSkels=explicit','exportSkin=explicit']
            elif skelRoot and skelOnly:
                options += ['exportSkels=auto','exportSkin=auto']
            if (int(cmds.about(version=True)) < 2022):
                f = cmds.file(filepath, force=True, options=';'.join(options), type="pxrUsdExport", pr=True, es=True)
            else:
                f = cmds.file(filepath, force=True, options=';'.join(options), type="USD Export", pr=True, es=True)

            if(f and publish_path != ''):
                if(cmds.referenceQuery(reparented_export_node, inr=True)):
                    export_node_pm = pm.PyNode(reparented_export_node)
                    rigref = pm.referenceQuery(export_node_pm, filename=True)
                    
                    modelrefs = pm.listReferences(parentReference=rigref, recursive=True)

                    stage = Usd.Stage.Open(f)

                    if ":" in stage.GetRootLayer().defaultPrim:
                        stage.GetRootLayer().defaultPrim = stage.GetRootLayer().defaultPrim.split(":")[-1]

                    #If there's a skeleton root, the CONTROLS were probably exported too. Delete them
                    if skelRoot:
                        controls_prim = None
                        for x in stage.GetDefaultPrim().GetChildren():
                            if "CONTROLS" in x.GetName() and x.GetParent() == stage.GetDefaultPrim():
                                controls_prim = x
                                break

                        if controls_prim:
                            stage.RemovePrim(controls_prim.GetPath())
                    

                    if not skelOnly:
                        mesh_xforms = list(set([pm.listRelatives(x, parent=True)[0] for x in pm.listRelatives(reparented_export_node, ad=True, type="mesh")]))

                        # Set Pref on meshes
                        for mesh in mesh_xforms:
                            try:
                                dag_path = mesh.longName()
                                add_renderman_ref_primvars(dag_path, mesh, stage)
                                
                            except:
                                child_mesh_success = False
                                for child_mesh in pm.listRelatives(mesh, children=True):
                                    try:
                                        if "Orig" not in child_mesh.name() and "Deformed" not in child_mesh.name():
                                            dag_path = mesh.longName()

                                            add_renderman_ref_primvars(dag_path, child_mesh, stage)
                                            break
                                    except:
                                        pass
                                
                                if not child_mesh_success:
                                    print("ERROR Setting Pref/Nref on",mesh.longName())
                            

                        modelref_updates = {}
                        for modelref in modelrefs:
                            #Add surfacing USD references to internal model references
                            fields = resolver.filepath_to_fields(modelref.path)
                            asset_type = fields['asset_type']
                            asset_name = fields['Asset']

                            if asset_type == 'camera':
                                continue

                            try:
                                template_steps = [(x, usd_utils.SG_TEMPLATE_MAP["Asset"][asset_type][x]) for x in usd_utils.SG_TEMPLATE_MAP["Asset"][asset_type] if x != "model" and x !="default"]
                                templates = []
                                for template in template_steps:
                                    for task in template[1]:
                                        templates += ['tank:/{0}/{1}?Step={2}&Task={3}&asset_type={4}&version=latest&Asset={5}'.format(shotgun_utils.get_project_code(), template[1][task]["template"], template[0], task, asset_type, asset_name)]
                            except Exception as e:
                                print("Could not find reference templates in usdUtils for " + asset_name)
                                continue

                            if len(templates) > 0:
                                #Get dag path of this modelref's root transform
                                modelref_dag_path = ""
                                if pm.referenceQuery(modelref, n=True, dp=True) == None:
                                    continue
                                for n in pm.referenceQuery(modelref, n=True, dp=True):
                                    node_parents = cmds.listRelatives(n, parent=True, f=True)

                                    #If node has exactly one parent
                                    if node_parents != None and len(node_parents) == 1:
                                        node_parent = node_parents[0]

                                        #If this node's parent is not a reference OR the parent is a reference but the filepath is not the same as this nodes filepath, then this node is the top transform of the reference
                                        if (not cmds.referenceQuery(node_parent, inr=True)) or (cmds.referenceQuery(node_parent, inr=True) and cmds.referenceQuery(node_parent, filename=True, wcn=True) != modelref.path):
                                            modelref_dag_path = cmds.ls(n,l=True)[0]
                                            break
                                if(reparented_export_node+"|" not in modelref_dag_path):
                                    continue
                                #Convert dag path with namespaces to SDF path
                                modelref_sdf_path = ""
                                for n in modelref_dag_path.split("|"):
                                    if ":" in n:
                                        modelref_sdf_path += n.split(":")[-1]
                                    else:
                                        modelref_sdf_path += n
                                    modelref_sdf_path += "/"
                                modelref_sdf_path = modelref_sdf_path[:-1]
                                print(modelref_dag_path)
                                print(modelref_sdf_path)

                                original_modelref_sdf_path = modelref_sdf_path
                                for oldPath in modelref_updates.keys():
                                    modelref_sdf_path = modelref_sdf_path.replace(oldPath, modelref_updates[oldPath])
                                modelref_updates[original_modelref_sdf_path] = modelref_sdf_path+"/geo"

                                prim = stage.GetPrimAtPath(modelref_sdf_path)
                                geoPath = modelref_sdf_path+"/geo"

                                #If a child named geo already exists, temporarily rename it so we don't overwrite it
                                if stage.GetPrimAtPath(geoPath):
                                    layer = stage.GetRootLayer()
                                    with Sdf.ChangeBlock():
                                        edits = Sdf.BatchNamespaceEdit()
                                        
                                        tempGeoPath = stage.GetPrimAtPath(geoPath).GetPath().ReplaceName("geoPUBLISHTEMP")
                                        edits.Add(Sdf.Path(geoPath), tempGeoPath)

                                        if not layer.Apply(edits):
                                            raise Exception("Could not apply layer edit")

                                #Move each child of the model under a geo prim. (So it matches our asset descriptions)
                                geoPrim = stage.DefinePrim(geoPath, "Xform")
                                layer = stage.GetRootLayer()

                                #Batch edits together
                                with Sdf.ChangeBlock():
                                    edits = Sdf.BatchNamespaceEdit()
                                    for child in prim.GetChildren():
                                        #Skip the child we just made named geo
                                        if child.GetName() != "geo":
                                            #If the prim is named geoPUBLISHTEMP, it used to be named geo. Rename it back to geo.
                                            if child.GetName() == "geoPUBLISHTEMP":
                                                newChildPath = geoPath+"/geo"
                                            else:
                                                newChildPath = geoPath+"/"+child.GetName()
                                            edits.Add(child.GetPath(),Sdf.Path(newChildPath))
                                    if not layer.Apply(edits):
                                        raise Exception("Could not apply layer edit")
                                
                                #Add templates from asset description to this prim. Add surfacing to geo child. (Matches asset description)
                                for template in templates:
                                    # if "Task=surfacing" in template:
                                    #     geoPrim.GetReferences().AddReference(template)
                                    # else:
                                    prim.GetReferences().AddReference(template)
                    
                    if frameHold > 1:
                        variantSets = stage.GetDefaultPrim().GetVariantSets()

                        frameHoldVS = variantSets.AddVariantSet("frameHold")

                        sourceFrameAttr = stage.GetDefaultPrim().CreateAttribute("sourceFrame", Sdf.ValueTypeNames.Int)

                        attrTimeSampleDict = {}
                        for prim in stage.Traverse():
                            for attr in prim.GetAttributes():
                                if attr.GetNumTimeSamples() > 0:
                                    timeSamples = attr.GetTimeSamples()
                                    attrTimeSampleDict[attr] = (timeSamples, [attr.Get(x) for x in timeSamples])
                                    attr.Clear()

                        for frameHoldVariant in range(0, frameHold):
                            frameHoldVS.AddVariant("heldFrom" + str(start_frame + frameHoldVariant))
                            frameHoldVS.SetVariantSelection("heldFrom" + str(start_frame + frameHoldVariant))

                            with frameHoldVS.GetVariantEditContext():
                                for attr, attrInfo in attrTimeSampleDict.items():
                                    timeSamples = attrInfo[0]
                                    timeSampleValues = attrInfo[1]

                                    value = timeSampleValues[0]
                                    lastSourceFrame = timeSamples[0]
                                    try:
                                        for i, timeSample in enumerate(timeSamples):
                                            if i % frameHold == frameHoldVariant:
                                                value = timeSampleValues[i]
                                                lastSourceFrame = timeSample
                                            sourceFrameAttr.Set(lastSourceFrame, timeSample)
                                            attr.Set(value, timeSample)
                                    except Exception as e:
                                        print(timeSample,timeSampleValues)
                                        raise Exception(e)
                        frameHoldVS.AddVariant("normal")
                        frameHoldVS.SetVariantSelection("normal")
                        with frameHoldVS.GetVariantEditContext():
                            for attr, attrInfo in attrTimeSampleDict.items():
                                timeSamples = attrInfo[0]
                                timeSampleValues = attrInfo[1]

                                for i, timeSample in enumerate(timeSamples):
                                    attr.Set(timeSampleValues[i], timeSample)
                                    sourceFrameAttr.Set(timeSample, timeSample)

                    if skelOnly:
                        rig_fields = resolver.filepath_to_fields(rig)

                        usd_rig_uri = 'tank:/{0}/{1}?Step=rig&Task=rig&asset_type={2}&version=latest&Asset={3}'.format(shotgun_utils.get_project_code(), RIG_USD_TEMPLATE_NAME, rig_fields['asset_type'], rig_fields['Asset'])
                        stage.GetDefaultPrim().GetReferences().AddReference(usd_rig_uri)
                    stage.GetRootLayer().Save()
    except Exception as e:
        print(traceback.format_exc())
        raise Exception(e)
    finally:
        delete_usd_user_properties(export_node, properties)

        if skelRoot and not skelOnly:
            cmds.deleteAttr('%s.USD_typeName' % skelRoot)