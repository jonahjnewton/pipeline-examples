import sgtk
import os

import mari
import mari_pipeline

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
                        engine.create_project(name=asset_name, sg_publishes=[latest_publish],channels_to_create=[],channels_to_import=[],project_meta_options={"Load":"All Models"},objects_to_load=[0])
                        print("Made project")

                        if int(os.environ.get("REZ_MARI_MAJOR_VERSION")) == 6:
                            template_file_name = "surfacing_channels"
                        elif int(os.environ.get("REZ_MARI_MAJOR_VERSION")) == 7:
                            template_file_name = "surfacing_channels_7"

                        # Import template channels
                        mari.session.importSession(f"{os.getenv('PROJ_ROOT')}/templates/surf/mariChannels/{template_file_name}/{template_file_name}.msf", [mari.geo.current()])
                        print("Imported template channels")
                        diffuseChannel = mari.geo.current().findChannel('diffuse')

                        if diffuseChannel != None:
                            try:
                                mari.geo.current().removeChannel(diffuseChannel, mari.geo.current().DESTROY_ALL)
                                print("Remove diffuse channel")
                            except Exception as e:
                                print(e)
                                pass
                        mari_pipeline.mari_preferences.MariPreferences()
                        return True
                    except Exception as e:
                        print(e)
                        pass
                #print((context.entity['name'],"tank:/{0}/maya_publish_asset_cache_fbx?Step=model&Task=model&asset_type={1}&version=latest&Asset={2}".format(os.environ.get('SHOTGUN_PROJECT'), self.__get_asset_type(context.entity['name'], shotgun), context.entity['name'])))
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