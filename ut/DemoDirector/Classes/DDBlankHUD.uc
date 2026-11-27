//=============================================================================
// DDBlankHUD - draws nothing. Swapped in by DDWatcher for clean cinematic shots
// (no HUD, crosshair, messages); the original HUD is restored afterwards.
//=============================================================================
class DDBlankHUD extends HUD;

simulated event PostRender(canvas Canvas) {}
simulated function Message(PlayerReplicationInfo PRI, coerce string Msg, name MsgType) {}
simulated function LocalizedMessage(class<LocalMessage> Message, optional int Switch, optional PlayerReplicationInfo RelatedPRI_1, optional PlayerReplicationInfo RelatedPRI_2, optional Object OptionalObject, optional string CriticalString) {}

defaultproperties
{
	RemoteRole=ROLE_None
}
