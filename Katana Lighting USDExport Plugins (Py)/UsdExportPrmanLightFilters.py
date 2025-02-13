from UsdExport.pluginAPI import BaseUsdExportPlugin
import Katana
import UsdKatana

import katana_pipeline.usdexport.light_filter as usdexport_light_filter

from fnpxr import UsdLux

class ALAUsdExportPrmanLightFilters(BaseUsdExportPlugin):

    #Run before mesh lights have been converted so any light:filters attributes are passed to the geo override
    priority = 1

    @staticmethod
    def WritePrim(stage, sdfLocationPath, attrDict):

        gaffer_parent_root = "/root/world/lgt"

        
        # Check for a material attribute group.
        materialAttrs = attrDict.get("material", None)
        referencePath = attrDict.get("referencePath", None)

        if materialAttrs:
            prim = stage.GetPrimAtPath(sdfLocationPath)
            if not prim:
                return
            print("Writing Light Filter: " + str(sdfLocationPath))

            if Katana.version[0] == 4 and Katana.version[1] == 5:
                lightApi = UsdKatana.LightAPI(prim)
            elif Katana.version[0] >= 5:
                lightApi = UsdKatana.KatanaLightAPI(prim)
            
            lightApi.Apply(prim)
            #UsdLux.ShadowAPI.Apply(prim)
            #UsdLux.ShapingAPI.Apply(prim)

            usdexport_light_filter.WriteLightFilter(stage,sdfLocationPath,materialAttrs)
            referencePathSdf = sdfLocationPath

        elif referencePath:
            print("Adding Light Filter Reference: " + str(sdfLocationPath))
            referencePathSdf = '/shot' + referencePath.getValue().split(gaffer_parent_root)[-1]
        else:
            return
        
        parentPrim = stage.GetPrimAtPath(sdfLocationPath.GetParentPath())

        # If the parent was a mesh light, we need to redirect the light filter to the mesh light
        if parentPrim.GetAttribute('meshLightRedirectPath'):
            parentPrim = stage.GetPrimAtPath(parentPrim.GetAttribute('meshLightRedirectPath').Get())

        if "Light" in parentPrim.GetTypeName() or "PxrMesh" in parentPrim.GetTypeName():
            parentLightApi = UsdLux.LightAPI(parentPrim)
            parentLightApiTarget = UsdLux.LightAPI.CreateFiltersRel(parentLightApi)
            parentLightApiTarget.AddTarget(referencePathSdf)

PluginRegistry = [
    ('UsdExport', 1, 'ALAUsdExportPrmanLightFilters', (['light filter', 'light filter reference'], ALAUsdExportPrmanLightFilters)),
]