from UsdExport.pluginAPI import BaseUsdExportPlugin

from fnpxr import UsdLux, Sdf

class ALAUsdExportMeshLightGeoOverrides(BaseUsdExportPlugin):

    priority = 0

    @staticmethod
    def WritePrim(stage, sdfLocationPath, attrDict):

        shot_parent_path = "/root/world/geo"

        
        prim = stage.GetPrimAtPath(sdfLocationPath)
        if not prim:
            return
        
        # Check for a material attribute group.
        materialAttrs = attrDict.get("material", None)
        if not materialAttrs:
            return
        
        geometryAttrs = attrDict.get("geometry", None)
        if not geometryAttrs:
            return
        
        areaLightGeometrySourceAttr = geometryAttrs.getChildByName("areaLightGeometrySource")
        if not areaLightGeometrySourceAttr:
            return

        print("Overriding geo to Mesh Light: " + str(sdfLocationPath))
        areaLightGeometrySourcePath = areaLightGeometrySourceAttr.getValue()

        areaLightGeometrySourcePrim = stage.DefinePrim(areaLightGeometrySourcePath.split(shot_parent_path)[1],"PxrMesh")

        meshLightAPI = UsdLux.MeshLightAPI(areaLightGeometrySourcePrim)
        meshLightAPI.Apply(areaLightGeometrySourcePrim)
        UsdLux.ShadowAPI.Apply(areaLightGeometrySourcePrim)

        lightAttributes = [x for x in prim.GetAuthoredAttributes() if "xformOp" not in x.GetName()]

        for attr in lightAttributes:
            attr.FlattenTo(areaLightGeometrySourcePrim, attr.GetName())

        # Used to redirect light filters to the mesh light
        redirectAttr = prim.CreateAttribute('meshLightRedirectPath', Sdf.ValueTypeNames.String)
        redirectAttr.Set(areaLightGeometrySourcePrim.GetPath().pathString)

PluginRegistry = [
    ('UsdExport', 1, 'ALAUsdExportMeshLightGeoOverrides', (['light'], ALAUsdExportMeshLightGeoOverrides)),
]