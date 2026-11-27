//=============================================================================
// DDBulletShine - translucent environment-mapped shell around the DDBullet mesh (polished metal highlight
// that does not spin with the bullet). Positioned by DDBullet every tick.
//=============================================================================
class DDBulletShine extends Effects;

defaultproperties
{
	DrawType=DT_Mesh
	Mesh=LodMesh'DemoDirector.DDBulletM'
	Style=STY_Translucent
	Texture=Texture'DemoDirector.Skins.DDShineTex'
	bMeshEnviroMap=True
	bUnlit=True
	ScaleGlow=0.5
	RemoteRole=ROLE_None
	Physics=PHYS_None
	LifeSpan=0
	bCollideActors=False
	bCollideWorld=False
}
