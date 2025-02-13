def export_usd_rig(node, filepath, destination, lookfile_uri, overrideRefs=True, overrideSkelProps=True, overrideSkelConstraints=True):
    """
    Exports rig to USD, replacing referenced geo with a reference to the USD geo, adding surfacing URIs,
    and converting parentConstraints to rigidbody constraints.

    :param node:
    :param filepath:
    :param destination:
    :param lookfile_uri:
    :param overrideRefs=True:
    :param overrideSkelProps=True:
    :param overrideSkelConstraints=True:
    :return:
    """
    node

    # make sure the lod node is selected prior exporting
    print("Dealing with node: %s" % (node))

    cmds.select(node, r=True)

    print("Changing to URI paths on node: %s" % node)
    change_to_uris(node)

    properties = [("filepath", destination), ("lookfileUri", lookfile_uri)]
    create_usd_user_properties(node, properties)

    joint_constraints = []

    if overrideSkelConstraints:
        for constraint in cmds.ls(type="parentConstraint", long=True):
            targets = cmds.parentConstraint(constraint, q=True,targetList=True)
            if not targets or len(targets) != 1:
                continue

            if cmds.objectType(targets[0]) != "joint":
                continue
            
            t = get_joint_path_string(targets[0])

            skel = get_skel_path_string(t.split("/")[0], node)

            weight = cmds.getAttr(constraint+"."+cmds.parentConstraint(constraint, q=True,weightAliasList=True)[0])

            skelprop = [("constraintTarget", t), ("skelPath",skel), ("constraintWeight",weight)]
            cmds.select(constraint, r=True)
            create_usd_user_properties(constraint, skelprop)

            joint_constraints.append(constraint)
    
    cmds.select(node, r=True)

    try:
        usd_export_options = ['shadingMode=none',
                                'exportRefsAsInstanceable=1',
                                'exportUVs=1',
                                'exportMaterialCollections=0',
                                'materialCollectionsPath=/Collections',
                                'exportColorSets=1',
                                'renderableOnly=0',
                                'mergeTransformAndShape=1',
                                'exportInstances=1',
                                'defaultMeshScheme=catmullClark',
                                'exportVisibility=1',
                                'animation=0',
                                'stripNamespaces=1',
                                'startTime=1',
                                'endTime=1',
                                'frameStride=1.0',
                                'exportSkels=auto',
                                'exportSkin=auto',]
        if (int(cmds.about(version=True)) < 2022):
            cmds.file(filepath,
                  force=True,
                  options=';'.join(usd_export_options),
                  type="pxrUsdExport",
                  exportSelected=True,
                  preserveReferences=True)
        else:
            refs = cmds.listRelatives(node, children=True, ad=True, f=True, type='mayaUsdProxyShape')  
            cmds.file(filepath,
                  force=True,
                  options=';'.join(usd_export_options),
                  type="USD Export",
                  exportSelected=True,
                  preserveReferences=True)
            
            stage = Usd.Stage.Open(filepath)
            controls_prim = None
            for x in stage.GetDefaultPrim().GetChildren():
                if "CONTROLS" in x.GetName():
                    controls_prim = x
                    break
        
            if controls_prim:
                stage.RemovePrim(controls_prim.GetPath())

            skelAttributes = {}
            skelRelationShips = {}
            skelConstraints = {}
            #constraintChildren = []

            if overrideSkelProps or overrideSkelConstraints:
                for prim in stage.Traverse():
                    if len(prim.GetPath().pathString.split("/")) < 3 or prim.GetPath().pathString.split("/")[2] != "GEO":
                        continue

                    attrList = prim.GetAuthoredAttributes()
                    for attr in attrList:
                        attrType = attr.GetTypeName()

                        # Get skel properties to reroute to referenced geo later
                        if attr.GetName().startswith('skel:') or ':skel:' in attr.GetName() and overrideSkelProps:
                            if not skelAttributes.get(prim.GetPath().pathString, None):
                                skelAttributes[prim.GetPath().pathString] = []
                            skelAttributes[prim.GetPath().pathString] += [(attr.GetName(),attrType, attr.Get(), prim.GetPath().pathString)]

                        # Get parentConstraint targets to replace with rigidbody skinning later
                        elif attr.GetName().endswith('constraintTarget') and overrideSkelConstraints:
                            parentPath = "/".join(prim.GetPath().pathString.split("/")[:-1])
                            skelConstraints[parentPath] = [(attr.Get(), prim.GetAttribute("userProperties:skelPath").Get(),prim.GetAttribute("userProperties:constraintWeight").Get(), parentPath)]
                            # constraintChildren += prim.GetChildren()
                    
                    if overrideSkelProps:
                        relList = prim.GetAuthoredRelationships()
                        for rel in relList:

                            if rel.GetName().startswith('skel:') or ':skel:' in rel.GetName():
                                if not skelRelationShips.get(prim.GetPath().pathString, None):
                                    skelRelationShips[prim.GetPath().pathString] = []
                                skelRelationShips[prim.GetPath().pathString] += [(rel.GetName(), rel.GetTargets(), prim.GetPath().pathString)]

            # Replace referenced models with reference queries to model USD
            modelref_updates = {}
            if refs != None and len(refs) > 0:
                for ref in refs:
                    ref_stage = Usd.Stage.Open(cmds.getAttr(ref+".filePath"))
                    #Add maya root translations to prim
                    #Copy root prim from ref stage to export stage
                    ref_parent_transform = cmds.listRelatives(ref, parent=True,f=True)[0]

                    ref_dag_root = ref_parent_transform.replace("|","/")

                    ref_stage_root_prim = ref_stage.GetDefaultPrim()
                    ref_stage_ref_prim = ref_stage.GetDefaultPrim().GetChildren()[0]

                    ref_stage_root_xform_vectors = UsdGeom.XformCommonAPI(ref_stage_root_prim).GetXformVectors(Usd.TimeCode.Default())
                    ref_stage_ref_xform_vectors = UsdGeom.XformCommonAPI(ref_stage_ref_prim).GetXformVectors(Usd.TimeCode.Default())

                    stage.DefinePrim(ref_dag_root+str(ref_stage_root_prim.GetPath()), 'Xform')
                    stage.DefinePrim(ref_dag_root+str(ref_stage_ref_prim.GetPath()), 'Xform')

                    stage_new_ref_root_prim = stage.GetPrimAtPath(ref_dag_root+str(ref_stage_root_prim.GetPath()))
                    stage_new_ref_ref_prim = stage.GetPrimAtPath(ref_dag_root+str(ref_stage_ref_prim.GetPath()))
                    
                    UsdGeom.XformCommonAPI(stage_new_ref_root_prim).SetXformVectors(ref_stage_root_xform_vectors[0], ref_stage_root_xform_vectors[1], ref_stage_root_xform_vectors[2], ref_stage_root_xform_vectors[3], ref_stage_root_xform_vectors[4], Usd.TimeCode.Default())
                    UsdGeom.XformCommonAPI(stage_new_ref_ref_prim).SetXformVectors(ref_stage_ref_xform_vectors[0], ref_stage_ref_xform_vectors[1], ref_stage_ref_xform_vectors[2], ref_stage_ref_xform_vectors[3], ref_stage_ref_xform_vectors[4], Usd.TimeCode.Default())

                    Usd.ModelAPI(stage_new_ref_ref_prim).SetKind("subcomponent")

                    stage_new_ref_ref_prim.GetReferences().AddReference(cmds.getAttr(ref+".descriptionUri"))

            if overrideRefs:
                modelrefs = [x for x in pm.listReferences(recursive=True) if "/model/" in str(x.path)]
                if modelrefs != None and len(modelrefs) > 0:
                    for modelref in modelrefs:
                        #Add surfacing USD references to internal model references
                        fields = resolver.filepath_to_fields(modelref.path)
                        asset_type = fields['asset_type']
                        asset_name = fields['Asset']
                        description_uri = 'tank:/{0}/{1}?Step=description&Task=description&asset_type={2}&version=latest&Asset={3}'.format(shotgun_utils.get_project_code(),ASSET_DESCRIPTION_TEMPLATE_NAME, asset_type, asset_name)

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

                        if(node+"|" not in modelref_dag_path):
                            continue

                        #Convert dag path with namespaces to SDF path
                        print("modelref_dag_path: " + modelref_dag_path)
                        modelref_sdf_path = ""
                        for n in modelref_dag_path.split("|"):
                            if ":" in n:
                                modelref_sdf_path += n.split(":")[-1]
                            else:
                                modelref_sdf_path += n
                            modelref_sdf_path += "/"
                        modelref_sdf_path = modelref_sdf_path[:-1]

                        print("modelref_sdf_path: " + modelref_sdf_path)

                        # Add /geo to geo path to fit our asset descriptions.
                        original_modelref_sdf_path = modelref_sdf_path
                        for oldPath in modelref_updates.keys():
                            modelref_sdf_path = modelref_sdf_path.replace(oldPath, modelref_updates[oldPath])
                        modelref_updates[original_modelref_sdf_path] = modelref_sdf_path+"/geo"

                        prim = stage.GetPrimAtPath(modelref_sdf_path)
                        xform_vectors = UsdGeom.XformCommonAPI(prim).GetXformVectors(Usd.TimeCode.Default())
                        stage.RemovePrim(modelref_sdf_path)
                        recreated_prim = stage.DefinePrim(modelref_sdf_path,'Xform')
                        UsdGeom.XformCommonAPI(recreated_prim).SetXformVectors(xform_vectors[0], xform_vectors[1], xform_vectors[2], xform_vectors[3], xform_vectors[4], Usd.TimeCode.Default())
                        Usd.ModelAPI(recreated_prim).SetKind("subcomponent")
                        recreated_prim.GetReferences().AddReference(description_uri)

                        # Get list of skel attributes and relationships for new referenced prims
                        if overrideSkelProps:
                            culledAttributes = skelAttributes.copy()
                            for path in skelAttributes.keys():
                                if path.startswith(modelref_sdf_path):
                                    newPath = path.replace(modelref_sdf_path, modelref_sdf_path + "/geo")
                                    currentValue = culledAttributes[path]
                                    culledAttributes[newPath] = currentValue.copy()
                                    del culledAttributes[path]
                            skelAttributes = culledAttributes.copy()

                            culledRelationships = skelRelationShips.copy()
                            for path in skelRelationShips.keys():
                                if path.startswith(modelref_sdf_path):
                                    newPath = path.replace(modelref_sdf_path, modelref_sdf_path + "/geo")
                                    currentValue = culledRelationships[path]
                                    culledRelationships[newPath] = currentValue.copy()
                                    del culledRelationships[path]
                            skelRelationShips = culledRelationships.copy()

                        # Get list of parentConstraint prims for new referenced prims
                        if overrideSkelConstraints:
                            culledConstraints = skelConstraints.copy()
                            for path in skelConstraints.keys():
                                if path.startswith(modelref_sdf_path):
                                    newPath = path.replace(modelref_sdf_path, modelref_sdf_path + "/geo")
                                    currentValue = culledConstraints[path]
                                    culledConstraints[newPath] = currentValue.copy()
                                    del culledConstraints[path]
                            skelConstraints = culledConstraints.copy()

                    stage.GetRootLayer().Save()
            
            if overrideSkelProps:
                for path in skelAttributes.keys():
                    print("Adding skel attributes to " + path)
                    #print(stage.GetPrimAtPath(path))
                    newPrim = stage.OverridePrim(path)
                    UsdSkel.BindingAPI.Apply(newPrim)
                    for attrTuple in skelAttributes[path]:
                        newAttr = newPrim.CreateAttribute(
                        attrTuple[0], attrTuple[1])

                        newAttr.Set(attrTuple[2])

                for path in skelRelationShips.keys():
                    print("Adding skel relationships to " + path)
                    #print(stage.GetPrimAtPath(path))
                    newPrim = stage.OverridePrim(path)
                    UsdSkel.BindingAPI.Apply(newPrim)
                    for relTuple in skelRelationShips[path]:
                        newRel = newPrim.CreateRelationship(
                        relTuple[0])

                        for target in relTuple[1]:
                            newRel.AddTarget(target)

            # Convert parentConstraints to rigidbody skins
            if overrideSkelConstraints:
                for path in skelConstraints.keys():
                    print("Applying parent constraint logic to " + path)
                    newPrim = stage.OverridePrim(path)
                    primSkel = UsdSkel.BindingAPI.Apply(newPrim)

                    for constraintTuple in skelConstraints[path]:
                        targetPath = constraintTuple[0]

                        skel = constraintTuple[1]

                        primSkel.CreateJointsAttr([targetPath])
                        primSkel.CreateJointIndicesPrimvar(constant=True,elementSize=1).Set([0])
                        primSkel.CreateJointWeightsPrimvar(constant=True,elementSize=1).Set([float(constraintTuple[2])])
                        
                        # Copy bind transform from siblings. TODO: Would be great if we could figure this out independantly.
                        bindTransform = None

                        xform = UsdGeom.Xformable(newPrim)
                        time = Usd.TimeCode.Default()
                        bindTransform = xform.ComputeLocalToWorldTransform(time)
                        
                        print("Computing bind transform for {0} from local xform.".format(path))
                        newPrim.GetAttribute("primvars:skel:geomBindTransform").Set(bindTransform)

                        primSkel.CreateSkeletonRel().AddTarget(skel)



            stage.GetRootLayer().Save()

    except Exception as e:
        print(traceback.format_exc())
        raise TankError("Failed to export USD File: %s" % e)
    finally:
        # tidy up the usd filePath attrs, as we don't want them hanging around in the scene after publish
        delete_usd_user_properties(node, properties)

        if overrideSkelConstraints:
            for constraint in joint_constraints:
                delete_usd_user_properties(constraint, [("constraintTarget",""),("skelPath","")])
