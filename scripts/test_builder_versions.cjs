/* Exercise the actual UI events without a plug, browser permissions or audio. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
function setup(search=''){
 const nodes=new Map(),events=new Map(),revoked=[],calls=[];
 const get=id=>{if(!nodes.has(id))nodes.set(id,{value:'',hidden:false,disabled:false,files:[],classList:{toggle(){}},addEventListener(name,fn){events.set(`${id}:${name}`,fn);},removeAttribute(name){delete this[name];}});return nodes.get(id);};
 const identities=['NAMLNK23','NAMLNK28','NAMLNK29'],recipes=Object.fromEntries(identities.map(identity=>[identity,{identity,output:{name:identity+'.bin'}}]));
 let pending=null;
 const scope={URLSearchParams,location:{search},document:{querySelector:get,querySelectorAll:()=>[]},crypto:{subtle:{}},Blob,Uint8Array,URL:{createObjectURL:()=>`blob:${calls.length}`,revokeObjectURL:u=>revoked.push(u)},MightyNamRecipes:recipes,MightyNamRecipe:recipes.NAMLNK29,MightyNamBuilder:{inputBytes:4,inspect:async()=>({version:'V3.0.5 Original'}),build:async(data,recipe)=>{calls.push(recipe.identity);if(pending)await pending;return {bytes:new Uint8Array(4),name:recipe.output.name,report:{identity:recipe.identity,output_sha256:recipe.identity}};}}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../docs/builder/ui.js'),'utf8'),scope);
 return {get,events,calls,revoked,block:p=>pending=p,select:async v=>{get('#firmware-version').value=v;await events.get('#firmware-version:change')();},file:async()=>{get('#stock-file').files=[{size:4,arrayBuffer:async()=>new ArrayBuffer(4)}];await events.get('#stock-file:change')();},build:()=>events.get('#build:click')()};
}
test('version links select only known recipes; changing version invalidates stale firmware and report downloads',async()=>{
 const u=setup('?firmware=NAMLNK28');assert.equal(u.get('#build').textContent,'Build NAMLNK28');
 await u.file();await u.build();assert.equal(u.get('#firmware-download').download,'NAMLNK28.bin');
 await u.select('NAMLNK23');assert.equal(u.get('#result').hidden,true);assert.equal(u.get('#firmware-download').href,undefined);assert.equal(u.get('#report-download').href,undefined);assert.equal(u.revoked.length,2);
 await u.build();assert.equal(u.get('#firmware-download').download,'NAMLNK23.bin');assert.match(u.get('#report-download').download,/NAMLNK23/);assert.deepEqual(u.calls,['NAMLNK28','NAMLNK23']);
 assert.equal(setup('?firmware=NAMLNK99').get('#build').textContent,'Build NAMLNK29');
});
test('in-flight builds lock version selection and retain the selected recipe until verified',async()=>{
 const u=setup();await u.file();let done;u.block(new Promise(r=>done=r));const building=u.build();
 assert.equal(u.get('#firmware-version').disabled,true);assert.equal(u.get('#stock-file').disabled,true);
 await u.select('NAMLNK23');done();await building;
 assert.equal(u.get('#firmware-download').download,'NAMLNK29.bin');assert.deepEqual(u.calls,['NAMLNK29']);
 assert.equal(u.get('#firmware-version').disabled,false);assert.equal(u.get('#stock-file').disabled,false);
});
test('the online version menu and both aliases load all three provenance-checked recipes',()=>{
 for(const file of ['builder.html','looper-builder.html']){
  const html=fs.readFileSync(require.resolve('../docs/'+file),'utf8');
  for(const folder of ['builder','builder-v28','looper-builder'])assert.ok(html.includes(`${folder}/recipe.js?v=0.6.0`));
  for(const id of ['NAMLNK23','NAMLNK28','NAMLNK29'])assert.ok(html.includes(`value="${id}"`));
 }
 const context={};vm.createContext(context);
 for(const folder of ['builder','builder-v28','looper-builder'])vm.runInContext(fs.readFileSync(require.resolve('../docs/'+folder+'/recipe.js'),'utf8'),context);
 assert.deepEqual(Object.keys(context.MightyNamRecipes),['NAMLNK23','NAMLNK28','NAMLNK29']);assert.equal(context.MightyNamRecipe.identity,'NAMLNK29');
});
