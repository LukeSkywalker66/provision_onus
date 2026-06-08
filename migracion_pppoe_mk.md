[lucasv@Nodo1_OLT_PUB] > {
{... :local targetUsers {"apvillcasana2";"apzohar";"avrivero2";"avsosalazarte3";"banconacion";"bibliomuni";"cgfl
orentin";"chvgauto";"ctquinteros";"daoviedo";"dcamano2";"dgchavero";"dhurvitz";"ejamuz3";"empereyra";"evgaraffin
i";"fapousset";"fcruz";"federar";"fffreytes";"fssamira";"hfjimenez";"hgallardo";"jabmoreno2";"jcarretero";"jddom
inguez";"jicarranza";"laoviedo";"ldmoyano";"lgzucarelli2";"lvgomez";"mafranget2";"mbramajo";"mbsalguero1";"mccor
tez";"mdrpalacio";"mdvidales";"mnrivera";"msanchez7";"multimedioslimitada";"municultura1";"municultura";"oacorte
z2";"osdamilano";"psantano";"radioverdad";"riesgotrabajo";"rjgallardo2";"rmariza";"rmzuniga1";"vfernandez";"vrui
z";"vtferreira"};
{... 
{... :foreach i in=[/ppp secret find] do={
{{...   :local sUser [/ppp secret get $i name];
{{...   
{{...   :local isTarget false;
{{...   :foreach u in=$targetUsers do={
{{{...     :if ($u = $sUser) do={ :set isTarget true }
{{{...   }
{{... 
{{...   :if ($isTarget = true) do={
{{{...     :local sPass [/ppp secret get $i password];
{{{...     :local sProf [/ppp secret get $i profile];
{{{...     :local sServ [/ppp secret get $i service];
{{{...     
{{{...     :put "/ppp secret add name=\"$sUser\" password=\"$sPass\" profile=\"$sProf\" service=$sServ";
{{{...   }
{{... }
{... }
/ppp secret add name="vfernandez" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="municultura" password="123" profile="FIBRA_25" service=pppoe
/ppp secret add name="federar" password="123" profile="vip" service=pppoe
/ppp secret add name="riesgotrabajo" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="fssamira" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="vtferreira" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="vruiz" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="radioverdad" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="lvgomez" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="hgallardo" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="rmzuniga1" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="jcarretero" password="123" profile="Suspendidos" service=pppoe
/ppp secret add name="mbramajo" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="mdvidales" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="cgflorentin" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="avsosalazarte3" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="mafranget2" password="123" profile="Suspendidos" service=pppoe
/ppp secret add name="fcruz" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="mccortez" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="jicarranza" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="banconacion" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="empereyra" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="mnrivera" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="dgchavero" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="jddominguez" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="osdamilano" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="dhurvitz" password="123" profile="Suspendidos" service=pppoe
/ppp secret add name="ldmoyano" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="mdrpalacio" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="psantano" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="rjgallardo2" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="bibliomuni" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="ctquinteros" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="municultura1" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="ejamuz3" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="fapousset" password="123" profile="FIBRA_25" service=pppoe
/ppp secret add name="mbsalguero1" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="chvgauto" password="123" profile="FIBRA3X" service=pppoe
/ppp secret add name="laoviedo" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="apzohar" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="oacortez2" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="lgzucarelli2" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="dcamano2" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="rmariza" password="123" profile="Suspendidos" service=pppoe
/ppp secret add name="apvillcasana2" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="multimedioslimitada" password="123" profile="FIBRA3X" service=pppoe
/ppp secret add name="daoviedo" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="jabmoreno2" password="123" profile="FIBRA50" service=pppoe
/ppp secret add name="msanchez7" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="fffreytes" password="123" profile="FIBRA_12" service=pppoe
/ppp secret add name="avrivero2" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="hfjimenez" password="123" profile="FIBRA_6" service=pppoe
/ppp secret add name="evgaraffini" password="123" profile="FIBRA_6" service=pppoe
[lucasv@Nodo1_OLT_PUB] > 
