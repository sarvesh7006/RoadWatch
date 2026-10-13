import {test} from 'node:test';
import assert from 'node:assert/strict';
import {EMPTY_LOCATION,createLocationController,locationPayload} from '../src/location.js';

function fixture(){
 const requests=[],cleared=[],states=[];
 const geo={watchPosition(success,error,options){requests.push({success,error,options});return requests.length;},clearWatch(id){cleared.push(id);}};
 const controller=createLocationController(()=>geo,state=>states.push(state));
 return {controller,requests,cleared,states};
}
function fix(latitude=19.076,longitude=72.8777,timestamp=Date.now()){
 return {coords:{latitude,longitude,accuracy:8},timestamp};
}

test('GPS pending blocks a silent unlocated save',()=>{
 const {controller}=fixture();controller.start();
 assert.throws(()=>locationPayload(controller.snapshot()),/Wait for device location/);
});
test('a valid GPS fix preserves latitude, longitude and accuracy',()=>{
 const {controller,requests}=fixture();controller.start();requests[0].success(fix());
 assert.deepEqual(locationPayload(controller.snapshot()),{latitude:19.076,longitude:72.8777,gps_accuracy:8});
});
test('timeout after a fix clears old coordinates and blocks save',()=>{
 const {controller,requests,cleared}=fixture();controller.start();requests[0].success(fix());requests[0].error({code:3});
 assert.equal(controller.snapshot().latitude,'');assert.equal(controller.snapshot().accuracy,null);
 assert.throws(()=>locationPayload(controller.snapshot()),/Device location failed/);assert.deepEqual(cleared,[1]);
});
test('permission denial can only proceed after explicit no-location choice or manual input',()=>{
 const {controller,requests}=fixture();controller.start();requests[0].error({code:1});
 assert.match(controller.snapshot().message,/permission was denied/);
 assert.throws(()=>locationPayload(controller.snapshot()));controller.clear();
 assert.deepEqual(locationPayload(controller.snapshot()),{latitude:null,longitude:null,gps_accuracy:null});
});
test('late callbacks cannot overwrite manual coordinates or a newer GPS request',()=>{
 const {controller,requests}=fixture();controller.start();controller.manual('latitude','-12.5');controller.manual('longitude','0');
 requests[0].success(fix());requests[0].error({code:3});
 assert.deepEqual(locationPayload(controller.snapshot()),{latitude:-12.5,longitude:0,gps_accuracy:null});
 controller.start();requests[0].success(fix());assert.equal(controller.snapshot().status,'pending');
 requests[1].success(fix(0,0));assert.equal(locationPayload(controller.snapshot()).latitude,0);
});
test('partial, out of range, and nonfinite coordinates are rejected',()=>{
 for(const [latitude,longitude] of [['19',''],['91','10'],['10','181'],['NaN','10'],['10','Infinity']]){
  assert.throws(()=>locationPayload({...EMPTY_LOCATION,status:'manual',latitude,longitude}));
 }
});
test('expired fixes cannot be saved',()=>{
 assert.throws(()=>locationPayload({...EMPTY_LOCATION,status:'ready',latitude:'19',longitude:'72',timestamp:Date.now()-31000}),/stale/);
});
test('unmount cancels the watch and ignores delayed callbacks',()=>{
 const {controller,requests,states,cleared}=fixture();controller.start();controller.dispose();requests[0].success(fix());
 assert.equal(states.length,1);assert.deepEqual(cleared,[1]);
});
test('unsupported geolocation reports an actionable error instead of a successful empty location',()=>{
 const c=createLocationController(()=>undefined,()=>{});c.start();assert.equal(c.snapshot().status,'error');assert.throws(()=>locationPayload(c.snapshot()));
});
