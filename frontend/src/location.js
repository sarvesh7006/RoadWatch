// Location capture is explicit: pending/failed GPS must never become a silent
// unlocated save or silently reuse a previous manual/device position.
export const EMPTY_LOCATION = {latitude:'', longitude:'', accuracy:null, timestamp:null, status:'none', message:''};

export function locationPayload(location, now=Date.now()) {
  if (location.status==='pending') throw Error('Wait for device location, enter coordinates manually, or choose Continue without location.');
  if (location.status==='error') throw Error('Device location failed. Retry, enter coordinates manually, or choose Continue without location.');
  if (location.status==='ready' && (!Number.isFinite(location.timestamp) || now-location.timestamp>30000 || location.timestamp>now+5000)) {
    throw Error('Device location is stale. Refresh device GPS or enter the observation coordinates manually.');
  }
  const lat=String(location.latitude).trim(), lon=String(location.longitude).trim();
  if (!lat && !lon) return {latitude:null, longitude:null, gps_accuracy:null};
  if (!lat || !lon) throw Error('Enter both latitude and longitude, or clear both.');
  const latitude=Number(lat), longitude=Number(lon);
  if (!Number.isFinite(latitude) || Math.abs(latitude)>90 || !Number.isFinite(longitude) || Math.abs(longitude)>180) {
    throw Error('Latitude must be between −90 and 90; longitude must be between −180 and 180.');
  }
  const accuracy=location.accuracy;
  if (accuracy!==null && (!Number.isFinite(accuracy) || accuracy<0)) throw Error('Invalid location accuracy. Refresh the device location.');
  return {latitude,longitude,gps_accuracy:accuracy};
}

export function createLocationController(getGeolocation, onChange, initial=EMPTY_LOCATION) {
  let state={...initial}, generation=0, watch=null, provider=null, disposed=false;
  const emit=next=>{state=next;if(!disposed)onChange(state);};
  function cancel(){generation++;if(watch!==null)provider?.clearWatch(watch);watch=null;}
  function clear(){cancel();emit({...EMPTY_LOCATION});}
  function manual(field,value){
    cancel();emit({...state,[field]:value,accuracy:null,timestamp:null,status:'manual',message:'Manual observation coordinates. These will be attached when you save.'});
  }
  function start(){
    cancel();const token=generation;
    emit({...EMPTY_LOCATION,status:'pending',message:'Waiting for device location… No location has been saved yet.'});
    const fail=e=>{
      if(disposed || token!==generation)return;
      cancel();
      const reason={1:'Location permission was denied. Allow location access in your browser or enter coordinates manually.',2:'This browser could not determine your location. Try a regular browser or enter coordinates manually.',3:'Location request timed out. Retry in a regular browser or enter coordinates manually.'}[e.code] || 'Device location is unavailable. Enter coordinates manually.';
      emit({...EMPTY_LOCATION,status:'error',message:reason});
    };
    try {
      provider=getGeolocation();
      if(!provider){fail({code:2});return;}
      const id=provider.watchPosition(p=>{
        if(disposed || token!==generation)return;
        const next={latitude:String(p.coords.latitude),longitude:String(p.coords.longitude),accuracy:p.coords.accuracy,timestamp:p.timestamp,status:'ready',message:`Device location ready · ±${Math.round(p.coords.accuracy)} m. This is your current device location, not the photo’s original location.`};
        try{locationPayload(next);emit(next);}catch{fail({code:2});}
      },fail,{enableHighAccuracy:true,maximumAge:5000,timeout:15000});
      if(disposed || token!==generation)provider.clearWatch(id);else watch=id;
    }catch{fail({code:2});}
  }
  return {start,manual,clear,snapshot:()=>state,dispose(){disposed=true;cancel();}};
}
