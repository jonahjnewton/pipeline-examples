import sgtk
import os
import re

import mari
import mari_pipeline

from fnpxr import Usd

HookClass = sgtk.get_hook_baseclass()


class SceneOperation(HookClass):
    """
    Hook called to perform an operation with the
    current scene
    """

    def execute(
        self,
        operation,
        file_path,
        context,
        parent_action,
        file_version,
        read_only,
        **kwargs
    ):
        """
        Main hook entry point

        :param operation:       String
                                Scene operation to perform

        :param file_path:       String
                                File path to use if the operation
                                requires it (e.g. open)

        :param context:         Context
                                The context the file operation is being
                                performed in.

        :param parent_action:   This is the action that this scene operation is
                                being executed for.  This can be one of:
                                - open_file
                                - new_file
                                - save_file_as
                                - version_up

        :param file_version:    The version/revision of the file to be opened.  If this is 'None'
                                then the latest version should be opened.

        :param read_only:       Specifies if the file should be opened read-only or not

        :returns:               Depends on operation:
                                'current_path' - Return the current scene
                                                 file path as a String
                                'reset'        - True if scene was reset to an empty
                                                 state, otherwise False
                                all others     - None
        """

        try:
            mari_pipeline.mari_preferences.workfiles_busy = True
            engine = sgtk.platform.current_engine()
            shotgun = engine.tank.shotgun

            asset_name = context.entity['name']

            # Mari doesn't have any scene operations, since it only works with the context change mode.
            # However workfiles does require that it can find the hook, so this is a placeholder hook.
            #tank:/s123/maya_publish_asset_cache_fbx?Step=model&Task=model&asset_type=character&version=latest&Asset=charHeroRobot01
        
            if operation == "reset":
                print("reset called")

                if(mari.projects.current() != None):
                    mari.projects.close(ConfirmIfModified=False)

                if parent_action == "new_file":
                    print("new_file called")

                     # Check if project with asset name exists, if so remove it
                    if(mari.projects.find(asset_name) != None):
                        mari.projects.remove(asset_name)
                        print("Removed project with asset name")
                    elif len([p for p in mari.projects.list() if "_".join(p.name().split("_")[:-1]) == asset_name]) > 0:
                        matching_project = [p for p in mari.projects.list() if "_".join(p.name().split("_")[:-1]) == asset_name][0]
                        mari.projects.remove(matching_project.name())
                        print("Removed project with similar name")

                    try:
                        print("Trying to create project")
                        latest_publish = shotgun.find_one("PublishedFile", [['entity.Asset.code', "is", asset_name], ['name', 'contains', '_model'],['name', 'not_contains', 'LOD'], ['published_file_type.PublishedFileType.code', "is", 'USD File'], ['project.Project.tank_name','is',os.getenv('SHOTGUN_PROJECT')]], fields = ["id", "version_number", "path"], order = [{'field_name':'version_number', 'direction':'desc'}])
                        print("Found latest publish: " + str(latest_publish))

                        stage = Usd.Stage.Open(latest_publish['path']['local_path'])

                        prim = stage.GetDefaultPrim()

                        model_variant_set = prim.GetVariantSet('model_variant')

                        variants = []
                        default_variant = None
                        if model_variant_set:
                            model_variant_set.GetVariantNames()
                            default_variant = model_variant_set.GetVariantSelection()

                            for name in model_variant_set.GetVariantNames():
                                variants.append(name)

                        engine.create_project(name=asset_name, sg_publishes=[latest_publish],channels_to_create=[],channels_to_import=[],project_meta_options={"Load":"All Models"},objects_to_load=[0])
                        print("Made project")

                        geo_default_name = mari.geo.current().name()

                        if default_variant:
                            mari.geo.current().setMetadata('Variants', prim.GetPath().StripAllVariantSelections().pathString+ "{model_variant=" + default_variant + "}")
                        elif len(variants) == 0:
                            applyALATemplate(mari.geo.current())

                        setupVariants(variants, latest_publish, prim.GetPath().StripAllVariantSelections().pathString, default_variant, geo_default_name, engine, default_geo=mari.geo.current())

                        mari_pipeline.mari_preferences.MariPreferences()
                        return True
                    except Exception as e:
                        print(e)
                        pass
                elif parent_action == "open_file":
                    print("open_file called")
                    return True
                
                return False
            elif operation == "save_as":
                # Archive the current project, rename it and extract the new project
                print("save_as called")
                currentProject = mari.projects.current()
                currentProjectName = currentProject.name()

                new_name = asset_name + "_" + file_path.split(".")[-2]
                currentProject.save(ForceSave=True)
                currentProject.close(ConfirmIfModified=False)

                mari.projects.rename(currentProjectName, new_name)

                currentProject = mari.projects.find(new_name)

                mari.projects.archive(new_name, file_path)
                mari.projects.remove(new_name)
                mari.projects.extract(file_path)
                mari.projects.open(new_name)
                
            elif operation == "open":
                # Remove the current project for the selected context and open the new one
                print("open called")
                if(mari.projects.current() != None):
                    mari.projects.close(ConfirmIfModified=False)

                if(mari.projects.find(asset_name) != None):
                    mari.projects.remove(asset_name)
                elif len([p for p in mari.projects.list() if "_".join(p.name().split("_")[:-1]) == asset_name]) > 0:
                    matching_project = [p for p in mari.projects.list() if "_".join(p.name().split("_")[:-1]) == asset_name][0]
                    mari.projects.remove(matching_project.name())

                project_to_open = mari.projects.extract(file_path)
                mari.projects.open(project_to_open.name())
        except Exception as e:
            raise Exception(e)
        finally:
            mari_pipeline.mari_preferences.workfiles_busy = False

def setupVariants(variant_names, sg_publish_data, root_prim_path, default_variant, geo_default_name, mari_engine, default_geo=None):
	variants_geo = []
	for variant in variant_names:
		# If we have default geo provided and the variant is the default variant, we don't need to load the geo again
		# But we still want to set up metadata later, so we add the default geo to the list
		if default_geo and variant == default_variant:
			variants_geo.append(default_geo)
			continue
		
		print("Adding new variant: " + variant)
		variants_geo += mari_engine.load_geometry(sg_publish = sg_publish_data, options = {"Load":"All Models", 'Variants': root_prim_path + "{model_variant=" + variant + "}"}, objects_to_load = [0])

	for geo in variants_geo:
		
		applyALATemplate(geo)

		geo_metadata = geo.metadata('Variants')
		if geo_metadata != None:
			geo_model_variant = re.search(r"model_variant=(\w+)}", geo_metadata)
			if geo_model_variant != None:
				geo_model_variant = geo_model_variant.group(1)
			
			# If geo doesn't have a specific model variant set, but does have a model_variant parameter, it's the default variant
			elif len(variant_names) > 0 and default_variant:
				geo_model_variant = default_variant
			
			if geo_model_variant != None:
				geo.setName(f"{geo_default_name}_{geo_model_variant}")
				geo.setMetadata('geo_default_name', geo_default_name)
				print(f"Set geo name to {geo.name()}")

				for shader in geo.shaderList():
					if not shader.shaderModel():
						continue
					elif shader.shaderModel().id() == "PxrSurface":
						shader.setName(f"{shader.name()}_{geo_model_variant}")

def applyALATemplate(geo):
	if int(os.environ.get("REZ_MARI_MAJOR_VERSION")) == 6:
		template_file_name = "surfacing_channels"
	elif int(os.environ.get("REZ_MARI_MAJOR_VERSION")) == 7:
		template_file_name = "surfacing_channels_7"
	
	mari.session.importSession(f"{os.getenv('PROJ_ROOT')}/templates/surf/mariChannels/{template_file_name}/{template_file_name}.msf", [geo])
	print("Imported template channels")
	diffuseChannel = geo.findChannel('diffuse')

	if diffuseChannel != None:
		try:
			geo.removeChannel(diffuseChannel, geo.DESTROY_ALL)
			print("Remove diffuse channel")
		except Exception as e:
			print(e)
		