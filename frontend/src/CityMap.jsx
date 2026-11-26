import React from 'react';
import { CircleMarker, MapContainer, TileLayer, Tooltip as MapTooltip } from 'react-leaflet';
import { CITY_CENTERS } from './cityCoordinates';
import 'leaflet/dist/leaflet.css';

const GEO_NAMES = 'https://www.geonames.org';

export default function CityMap({ data=[], selectedCity='', onCitySelect=()=>{}, height=390 }) {
  const points=data.filter(row=>CITY_CENTERS[row.city]);
  const maxOrders=Math.max(...points.map(row=>Number(row.total_orders||0)),1);
  const selected=selectedCity?CITY_CENTERS[selectedCity]:null;
  const center=selected?[selected.lat,selected.lon]:[22.7,79.1];
  const zoom=selected?7:4.3;
  return <div className="city-map-wrap">
    {points.length ? <MapContainer key={`${selectedCity||'india'}-${points.length}`} center={center} zoom={zoom} zoomSnap={.25} scrollWheelZoom={false} className="city-map" style={{height}}>
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"/>
      {points.map(row=>{
        const city=CITY_CENTERS[row.city];
        const orders=Number(row.total_orders||0);
        const radius=selectedCity===row.city?18:Math.max(8,Math.min(17,7+10*Math.sqrt(orders/maxOrders)));
        return <CircleMarker key={row.city} center={[city.lat,city.lon]} radius={radius}
          pathOptions={{color:'#ffffff',weight:3,fillColor:selectedCity===row.city?'#e99c4a':'#138574',fillOpacity:.88,className:'city-marker'}}
          eventHandlers={{click:()=>onCitySelect(row.city)}}>
          <MapTooltip direction="top" offset={[0,-8]} opacity={1}>
            <div className="map-tooltip"><b>{row.city}</b><span>{Number(orders).toLocaleString('en-IN')} orders</span><span>Revenue ₹{Number(row.revenue||0).toLocaleString('en-IN',{maximumFractionDigits:0})}</span><span>{Number(row.cancellation_rate||0).toFixed(1)}% cancelled</span><small>Click to filter dashboard</small></div>
          </MapTooltip>
        </CircleMarker>;
      })}
    </MapContainer> : <div className="map-empty">City coordinates are not available for the current rows.</div>}
    {points.length>0&&<div className="map-footer"><span><i/>Circle size reflects order volume</span><a href={`${GEO_NAMES}/${CITY_CENTERS[selectedCity||points[0]?.city]?.geonames}`} target="_blank" rel="noreferrer">GeoNames city-centre reference ↗</a><a href="https://www.openstreetmap.org/fixthemap" target="_blank" rel="noreferrer">Report map issue</a></div>}
    <p className="map-note">Markers represent city centres and aggregate city metrics; no customer, restaurant or live-driver locations are in the dataset. Map tiles © OpenStreetMap contributors.</p>
  </div>;
}
