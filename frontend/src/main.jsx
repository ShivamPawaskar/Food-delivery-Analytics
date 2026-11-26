import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity, ArrowUpRight, BarChart3, Bike, CalendarDays, Check,
  ChevronDown, CircleHelp, Clock3, Database, Download, FileBarChart2, Filter,
  LayoutDashboard, MapPin, Menu, Search, Settings2, ShieldCheck, ShoppingBag, Upload,
  Store, TrendingUp, Users, Utensils, X, Zap,
} from 'lucide-react';
import CityMap from './CityMap';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart,
  Pie, PieChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts';
import './styles.css';

const API = import.meta.env.VITE_API_URL || '';
const COLORS = ['#148477', '#59b8a8', '#f3a85a', '#8095f5', '#d1788b', '#87b877'];
const NAV = [
  { group: 'WORKSPACE', items: [
    ['Overview', LayoutDashboard], ['Orders', ShoppingBag], ['Forecast', TrendingUp], ['Restaurants', Store], ['Delivery', Bike], ['Customers', Users], ['Cities', MapPin],
  ]},
  { group: 'OPERATIONS', items: [
    ['Data Quality', ShieldCheck], ['ETL Monitor', Activity], ['Upload Analysis', Upload], ['Reports', FileBarChart2], ['About', CircleHelp],
  ]},
];
const PAGE_QUERIES = {
  Overview: ['overall_kpis','daily_advanced_trends','order_status_distribution','top_restaurants_by_revenue','cuisine_analytics','vehicle_type_comparison','city_analytics'],
  Orders: ['overall_kpis','daily_advanced_trends','monthly_advanced_trends','orders_by_payment_method','order_status_distribution','peak_ordering_hours','weekday_weekend_performance','average_order_value_trends','orders_by_weekday_hour'],
  Forecast: ['overall_kpis'],
  Restaurants: ['top_restaurants_by_revenue','top_restaurants_by_orders','restaurant_ratings','cuisine_analytics'],
  Delivery: ['overall_kpis','delivery_time_distribution','delivery_partner_analytics','vehicle_type_comparison','city_vehicle_delivery','delivery_distance_scatter','city_analytics'],
  Customers: ['customer_kpis','customer_frequency','customer_spending_distribution','top_customers_by_spend'],
  Cities: ['city_analytics'],
  'Data Quality': ['latest_quality_run','latest_etl_runs'],
  'ETL Monitor': ['latest_etl_runs'],
};
const TOUR_STEPS = [
  {page:'Overview',target:'tour-overview',title:'Welcome to DailyDish',body:'This is your operations snapshot. These cards summarize real orders, completed deliveries, cancellations, revenue, and service performance.',hint:'These numbers follow the active filters.'},
  {page:'Overview',target:'tour-filters',title:'Change what you’re looking at',body:'Choose a date range, city, restaurant, cuisine, payment method, or order status. The applicable dashboard queries refresh with those choices.',hint:'Try a city filter to explore one market.'},
  {page:'Orders',target:'tour-orders',title:'Find ordering patterns',body:'This calendar shows volume by day. The charts below break activity down by month, payment method, hour, and weekday.',hint:'Hover over chart marks for exact values.'},
  {page:'Forecast',target:'tour-scenario',title:'Try your own business scenario',body:'Enter an expected order count and average order value. Dash calculates estimated completed orders and revenue using the selected data’s completion rate.',hint:'Edit either value; the result updates instantly.'},
  {page:'Restaurants',target:'tour-restaurants',title:'Compare restaurant performance',body:'Each dot is a restaurant. Its position compares rating with revenue, and its size shows order volume.',hint:'Hover over a dot to see its details.'},
  {page:'Delivery',target:'tour-delivery',title:'Compare delivery operations',body:'Compare average delivery time by city and vehicle type, then explore delivery partners, distance, and late deliveries.',hint:'Use the global filters to narrow the comparison.'},
  {page:'Customers',target:'tour-customers',title:'Understand customer activity',body:'Review repeat customers, order frequency, spending buckets, and top spenders. Spending uses completed orders only.',hint:'Cancelled orders do not count as customer spend.'},
  {page:'Cities',target:'tour-cities',title:'Explore the city map',body:'Markers show city-level order activity using reference city-centre coordinates. Select a marker to filter the rest of the dashboard.',hint:'The map does not show live rider locations.'},
  {page:'Data Quality',target:'tour-quality',title:'Inspect data quality',body:'See accepted and rejected source records, rejection reasons, and the records held aside from processed orders.',hint:'Download the rejection report from this section.'},
  {page:'ETL Monitor',target:'tour-etl',title:'Track ETL runs',body:'Check recent pipeline status and how many records entered, passed, or were rejected in each run.',hint:'Run the ETL to create a new audit entry.'},
  {page:'Upload Analysis',target:'tour-upload',title:'Analyze a file of your own',body:'Upload a CSV to inspect its columns, missing values, duplicates, numeric summaries, and distributions. The file is analyzed temporarily and does not enter PostgreSQL.',hint:'Use a CSV file up to 10 MB.'},
  {page:'Reports',target:'tour-reports',title:'Export useful reports',body:'Choose a report to download filtered orders, restaurant, delivery, city, or customer analytics as CSV.',hint:'Active filters are applied to each export.'},
  {page:'About',target:'tour-about',title:'Follow the data flow',body:'This diagram shows how source files move through validation and PostgreSQL before becoming dashboard analytics.',hint:'You’ve explored the whole workspace. Replay this tour any time.'},
];

function fmt(value, kind='number') {
  const n = Number(value || 0);
  if (kind === 'money') return new Intl.NumberFormat('en-IN', {style:'currency',currency:'INR',maximumFractionDigits:0}).format(n);
  if (kind === 'percent') return `${n.toFixed(1)}%`;
  if (kind === 'decimal') return n.toFixed(1);
  return new Intl.NumberFormat('en-IN', {maximumFractionDigits:0}).format(n);
}
function dateLabel(v) { return v ? new Date(v).toLocaleDateString('en-IN',{day:'2-digit',month:'short'}) : ''; }
function rows(payload) { return payload?.data || []; }

async function apiGet(path) {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) {
    const message = await response.json().catch(() => ({}));
    throw new Error(message.detail || `Request failed (${response.status})`);
  }
  return response.json();
}
function queryUrl(name, filters, extra={}) {
  const params = new URLSearchParams();
  Object.entries({...filters,...extra}).forEach(([key,value]) => { if (value !== '' && value != null) params.set(key,value); });
  if (!params.has('limit')) params.set('limit', name === 'filtered_orders' ? '5000' : '500');
  return `/api/query/${name}?${params.toString()}`;
}

function App() {
  const [page,setPage] = useState('Overview');
  const [mobileOpen,setMobileOpen] = useState(false);
  const [options,setOptions] = useState(null);
  const [filters,setFilters] = useState({start_date:'',end_date:'',city:'',restaurant_id:'',cuisine:'',payment_method:'',order_status:''});
  const [data,setData] = useState({});
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState('');
  const [search,setSearch] = useState('');
  const [searchResults,setSearchResults] = useState(null);
  const [searching,setSearching] = useState(false);
  const [connected,setConnected] = useState(false);
  const [guideOpen,setGuideOpen] = useState(false);
  const [tourStep,setTourStep] = useState(-1);
  const filterKey = JSON.stringify(filters);

  useEffect(() => {
    apiGet('/api/filters').then((o) => {
      setOptions(o);
      setFilters(f => ({...f,start_date:f.start_date || o.min_date || '',end_date:f.end_date || o.max_date || ''}));
    }).catch(e => setError(e.message));
    apiGet('/api/health').then(() => setConnected(true)).catch(() => setConnected(false));
  },[]);

  useEffect(() => {
    const names = PAGE_QUERIES[page] || [];
    if (!options || !names.length) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true); setError('');
    Promise.all(names.map(async name => [name, await apiGet(queryUrl(name,filters))]))
      .then(async results => {
        const resultMap = Object.fromEntries(results);
        const executionId = rows(resultMap.latest_quality_run)[0]?.execution_id;
        if (page === 'Data Quality' && executionId) {
          resultMap.rejected_records = await apiGet(queryUrl('rejected_records', {}, {execution_id:executionId,limit:1000}));
        }
        if (!cancelled) setData(resultMap);
      })
      .catch(e => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  },[page,filterKey,options]);

  const update = (key,value) => setFilters(current => ({...current,[key]:value}));
  const runSearch = async (event) => {
    event?.preventDefault();
    if (!search.trim()) return;
    setSearching(true); setSearchResults(null); setError('');
    try { setSearchResults(rows(await apiGet(queryUrl('quick_order_search',filters,{search_term:search.trim(),limit:100})))); }
    catch(e) { setError(e.message); }
    finally { setSearching(false); }
  };
  const exportCsv = async (name,extra={}) => {
    try {
      const params = new URLSearchParams();
      Object.entries({...filters,...extra,limit:'50000'}).forEach(([key,value])=>{if(value!==''&&value!=null)params.set(key,value)});
      const res = await apiGet(`/api/export/${name}?${params}`);
      const url = URL.createObjectURL(new Blob([res.csv],{type:'text/csv;charset=utf-8'}));
      const a = document.createElement('a'); a.href=url; a.download=res.filename; a.click(); URL.revokeObjectURL(url);
    } catch(e) { setError(e.message); }
  };
  const selectPage = name => { setPage(name); setMobileOpen(false); setSearchResults(null); };
  const startTour = () => { setGuideOpen(true); setTourStep(0); selectPage(TOUR_STEPS[0].page); };
  const moveTour = offset => {
    const next=tourStep+offset;
    if(next<0||next>=TOUR_STEPS.length){setTourStep(-1);selectPage('Overview');return;}
    setTourStep(next);selectPage(TOUR_STEPS[next].page);
  };

  return <div className="app-shell">
    {mobileOpen && <button className="mobile-scrim" aria-label="Close menu" onClick={()=>setMobileOpen(false)} />}
    <aside className={`sidebar ${mobileOpen?'sidebar-open':''}`}>
      <div className="brand"><div className="brand-mark"><Utensils size={20}/></div><div><b>daily<span>dish</span></b><small>DELIVERY INTELLIGENCE</small></div><button className="mobile-close icon-btn" onClick={()=>setMobileOpen(false)}><X size={18}/></button></div>
      <div className="workspace-switch"><div className="workspace-avatar">FD</div><div className="workspace-label"><b>Food Delivery</b><small>Analytics workspace</small></div><ChevronDown size={15}/></div>
      <nav className="side-nav">{NAV.map(section=><div className="nav-group" key={section.group}><p>{section.group}</p>{section.items.map(([name,Icon])=><button key={name} className={`nav-item ${page===name?'active':''}`} onClick={()=>selectPage(name)}><Icon size={18}/><span>{name}</span>{page===name&&<span className="nav-active-dot"/>}</button>)}</div>)}</nav>
      <div className="sidebar-bottom"><div className={`db-status ${connected?'online':''}`}><span className="status-dot"/><div><b>{connected?'Database connected':'Database offline'}</b><small>PostgreSQL · live data</small></div><Database size={16}/></div><div className="user-box"><div className="user-avatar">A</div><div><b>Analytics Admin</b><small>Project workspace</small></div><Settings2 size={17}/></div></div>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="top-left"><button className="mobile-menu icon-btn" onClick={()=>setMobileOpen(true)}><Menu size={20}/></button><div className="breadcrumbs">Workspace <span>/</span> <b>{page}</b></div></div><div className="top-actions"><form className="search-box" onSubmit={runSearch}><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search orders, restaurants…"/><button className="search-submit" aria-label="Search orders" title="Search orders" disabled={searching}><Search size={14}/></button></form><span className={`live-pill ${connected?'':'offline'}`}><i/>{connected?'Live database':'Offline'}</span><div className="top-avatar">A</div></div></header>
      <section className="content-area">
        <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> DELIVERY PERFORMANCE</div><h1>{page === 'Overview' ? 'Good morning. Here’s your overview.' : page}</h1><p>{subtitle(page)}</p></div><div className="updated-label"><span className="pulse-dot"/> Connected to PostgreSQL</div></div>
        {searchResults && <section className="search-results panel"><div className="panel-heading"><div><h2>Search results</h2><p>{searchResults.length} matching records for “{search}”</p></div><div className="search-result-actions"><button className="button-secondary" onClick={()=>downloadRows(searchResults,'order_search.csv')}><Download size={14}/>CSV</button><button className="icon-btn" onClick={()=>setSearchResults(null)}><X size={18}/></button></div></div><DataTable data={searchResults}/></section>}
        {page!=='Upload Analysis'&&<FilterBar options={options} filters={filters} update={update}/>}
        {error && page!=='Upload Analysis' && <div className="error-banner"><div><b>Couldn’t load dashboard data</b><span>{error}</span></div><button onClick={()=>window.location.reload()}>Retry</button></div>}
        {!options && !error && <div className="loading-state"><div className="spinner"/><b>Connecting to PostgreSQL</b><span>Preparing your analytics workspace…</span></div>}
        {page==='Upload Analysis' ? <UploadAnalysis/> : options && !error && <>{loading ? <div className="loading-inline"><div className="spinner small"/>Refreshing live analytics…</div> : renderPage(page,data,filters,exportCsv,selectPage,city=>update('city',city))}</>}
      </section>
      <footer className="footer"><span>DAILYDISH ANALYTICS</span><span>PostgreSQL backed · Filtered in real time</span></footer>
    </main>
    <GuideMascot open={guideOpen} setOpen={setGuideOpen} step={tourStep} setStep={setTourStep} onStart={startTour} onMove={moveTour}/>
  </div>;
}

function GuideMascot({open,setOpen,step,setStep,onStart,onMove}) {
  const current=step>=0?TOUR_STEPS[step]:null;
  const [position,setPosition]=useState(null);
  useEffect(()=>{
    if(!open||!current){setPosition(null);return;}
    setPosition(null);
    let cancelled=false,targetElement=null,observer=null,sizeObserver=null,timeout=null,raf=null;
    const fallback={ 'tour-overview':'.welcome-banner','tour-filters':'.filter-bar','tour-reports':'.report-grid' };
    const locate=()=>document.querySelector(`[data-tour-id="${current.target}"]`)||(fallback[current.target]?document.querySelector(fallback[current.target]):null);
    const placeCard=()=>{
      if(cancelled||!targetElement?.isConnected)return;
      const rect=targetElement.getBoundingClientRect(),card=document.querySelector('.guided-tour-card'),cardWidth=card?.getBoundingClientRect().width||Math.min(360,window.innerWidth-28),cardHeight=card?.offsetHeight||275,gap=16;
      let left,top,side;
      if(rect.right+gap+cardWidth<=window.innerWidth-12){left=rect.right+gap;top=rect.top+Math.min(22,Math.max(0,rect.height/2-100));side='left';}
      else if(rect.left-cardWidth-gap>=12){left=rect.left-cardWidth-gap;top=rect.top+Math.min(22,Math.max(0,rect.height/2-100));side='right';}
      else {left=Math.max(12,Math.min(window.innerWidth-cardWidth-12,rect.left));top=rect.bottom+gap+cardHeight<window.innerHeight?rect.bottom+gap:Math.max(12,rect.top-cardHeight-gap);side=top>rect.top?'top':'bottom';}
      if(top+cardHeight>window.innerHeight-12)top=window.innerHeight-cardHeight-12;
      setPosition({left,top:Math.max(12,top),side});
    };
    const findTarget=()=>{
      if(cancelled)return;
      if(targetElement?.isConnected){placeCard();return;}
      const found=locate();
      if(!found)return;
      targetElement=found;
      targetElement.scrollIntoView({behavior:'auto',block:'center'});
      targetElement.classList.add('guide-highlight');
      sizeObserver?.disconnect();sizeObserver=new ResizeObserver(placeCard);sizeObserver.observe(targetElement);
      raf=requestAnimationFrame(placeCard);
    };
    findTarget();
    observer=new MutationObserver(()=>{
      if(targetElement&&!targetElement.isConnected){targetElement.classList.remove('guide-highlight');targetElement=null;setPosition(null);}
      findTarget();
    });
    observer.observe(document.body,{childList:true,subtree:true});
    window.addEventListener('scroll',placeCard,true);window.addEventListener('resize',placeCard);
    timeout=setTimeout(()=>{if(!targetElement?.isConnected)setPosition(null);},15000);
    return ()=>{cancelled=true;observer?.disconnect();sizeObserver?.disconnect();clearTimeout(timeout);cancelAnimationFrame(raf);window.removeEventListener('scroll',placeCard,true);window.removeEventListener('resize',placeCard);targetElement?.classList.remove('guide-highlight');};
  },[open,step,current?.target]);
  return <div className="guide-dock">
    {open&&<section className={`guide-card ${current?'guided-tour-card':''} ${position?`guide-side-${position.side}`:''}`} style={current&&position?{left:position.left,top:position.top}:undefined} role="dialog" aria-label="DailyDish guided tour" aria-live="polite">
      <div className="guide-card-head"><div className="mascot-pop"><MascotFace/></div><div><b>Dash <span>your dashboard guide</span></b><small>{current?`STEP ${step+1} OF ${TOUR_STEPS.length}`:'A quick tour of your workspace'}</small></div><button className="icon-btn guide-close" aria-label="Close guide" onClick={()=>{setOpen(false);setStep(-1)}}><X size={16}/></button></div>
      {current?<><div className="guide-progress"><i style={{width:`${(step+1)/TOUR_STEPS.length*100}%`}}/></div><div className="guide-copy"><h3>{current.title}</h3><p>{current.body}</p><small><Zap size={13}/>{current.hint}</small></div><div className="guide-actions"><button className="button-secondary" onClick={()=>onMove(-1)} disabled={step===0}>Back</button><button className="button-primary" onClick={()=>onMove(1)}>{step===TOUR_STEPS.length-1?'Finish tour':'Next'} <ArrowUpRight size={14}/></button></div></>
      :<><div className="guide-copy"><h3>Hi, I’m Dash!</h3><p>I can show you how to explore the dashboard, understand its charts, and try the forecast scenario.</p><small><MapPin size={13}/>The tour guides you across each page.</small></div><div className="guide-actions"><button className="button-primary guide-start" onClick={onStart}>Take the guided tour <ArrowUpRight size={14}/></button></div></>}
    </section>}
    <button className={`guide-fab ${open?'guide-fab-open':''}`} onClick={()=>setOpen(v=>!v)} aria-label={open?'Close Dash guide':'Open Dash guide'} title="Meet Dash, your dashboard guide"><MascotFace/><span>{open?'Close guide':'Guide me'}</span><i/></button>
  </div>;
}
function MascotFace() {return <svg className="mascot-face" viewBox="0 0 52 52" role="img" aria-label="Dash mascot"><path d="M17 10V7.5a9 9 0 0 1 18 0V10" fill="none" stroke="#168477" strokeWidth="3" strokeLinecap="round"/><rect x="7" y="10" width="38" height="35" rx="12" fill="#e5f4ef" stroke="#168477" strokeWidth="2"/><path d="M19 7c2-4 7-5 10-2-3 0-5 2-6 5" fill="#83b779"/><circle cx="19" cy="26" r="2.2" fill="#24463d"/><circle cx="33" cy="26" r="2.2" fill="#24463d"/><path d="M20 33c3.5 4 8.5 4 12 0" fill="none" stroke="#168477" strokeWidth="2.4" strokeLinecap="round"/><circle cx="13" cy="32" r="2.2" fill="#f0b59d"/><circle cx="39" cy="32" r="2.2" fill="#f0b59d"/></svg>}

function subtitle(page) {
  return ({Overview:'A clear picture of your delivery operations, powered by live order data.',Orders:'Understand demand, ordering patterns, payments and revenue over time.',Forecast:'Explore a weekday-based demand forecast with a rolling historical backtest.',Restaurants:'Compare restaurant demand, revenue and service quality.',Delivery:'Track speed, reliability and performance across the delivery network.',Customers:'Explore customer activity and completed-order spending.',Cities:'Compare demand and delivery outcomes across cities.','Data Quality':'Review validation outcomes and inspect records held for data quality.', 'ETL Monitor':'Track pipeline runs and the status of incoming data.','Upload Analysis':'Upload a CSV for a quick, temporary data profile and visual analysis.',Reports:'Download live filtered analytics for your team.',About:'A transparent view of how source records become business decisions.'})[page];
}

function UploadAnalysis() {
  const [file,setFile]=useState(null),[result,setResult]=useState(null),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const chooseFile=next=>{if(!next)return;setError('');setResult(null);if(!next.name.toLowerCase().endsWith('.csv')){setFile(null);setError('Please choose a .csv file.');return;}if(next.size>10*1024*1024){setFile(null);setError('The maximum file size is 10 MB.');return;}setFile(next);};
  const analyze=async event=>{event.preventDefault();if(!file)return;setBusy(true);setError('');setResult(null);try{const form=new FormData();form.append('file',file);const response=await fetch(`${API}/api/upload-analysis`,{method:'POST',body:form});const payload=await response.json().catch(()=>({}));if(!response.ok)throw new Error(payload.detail||`Upload failed (${response.status})`);setResult(payload);const first=payload.profile.find(x=>x.data_type==='numeric')||payload.profile[0];setSelected(first?.column||'');}catch(e){setError(e.message)}finally{setBusy(false)}};
  const chartData=result?.charts?.[selected]||[],selectedProfile=result?.profile?.find(x=>x.column===selected);
  return <><div className="upload-hero"><div><span className="forecast-tag"><Upload size={14}/> QUICK FILE EXPLORER</span><h2>Bring a CSV. Get a clear picture.</h2><p>Profile columns, find missing data, and explore distributions without loading your file into the project database.</p></div><div className="upload-hero-mark"><FileBarChart2 size={30}/></div></div>
    <div className="upload-layout"><Panel title="Upload your data" sub="CSV only · up to 10 MB and 100,000 rows" className="upload-panel"><form onSubmit={analyze}><label className={`upload-dropzone ${file?'has-file':''}`} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();chooseFile(e.dataTransfer.files?.[0])}}><input type="file" accept=".csv,text/csv" onChange={e=>chooseFile(e.target.files?.[0])}/><div className="upload-icon"><Upload size={21}/></div><b>{file?file.name:'Drop your CSV here'}</b><span>{file?`${(file.size/1024).toFixed(1)} KB · ready to analyze`:'or click to browse files'}</span></label><div className="upload-actions"><span><ShieldCheck size={14}/>Processed temporarily, not retained</span><button className="button-primary" type="submit" disabled={!file||busy}>{busy?<><span className="spinner tiny"/>Analyzing file…</>:<><BarChart3 size={15}/>Analyze file</>}</button></div></form>{error&&<div className="upload-error">{error}</div>}</Panel><Panel title="What you’ll get" sub="A quick first look at the data"><div className="upload-benefits"><div><Check size={15}/><span>Rows, columns, duplicates and missing cells</span></div><div><Check size={15}/><span>Numeric summaries and category counts</span></div><div><Check size={15}/><span>Interactive column chart and data preview</span></div></div><p className="model-footnote">Uploads are processed temporarily, not retained, written to PostgreSQL, or mixed with the food-delivery analytics.</p></Panel></div>
    {result&&<><div className="upload-file-caption"><b>{result.filename}</b><span>{fmt(result.row_count)} rows · {fmt(result.column_count)} columns</span><button className="button-secondary" onClick={()=>{setResult(null);setFile(null)}}>Analyze another file</button></div><div className="metric-grid"><MetricCard label="Rows" value={fmt(result.row_count)} sub="Read from uploaded CSV" icon={Database}/><MetricCard label="Columns" value={fmt(result.column_count)} sub="Available for exploration" icon={FileBarChart2} tone="violet"/><MetricCard label="Missing cells" value={fmt(result.missing_cells)} sub="Across all columns" icon={Activity} tone="gold"/><MetricCard label="Duplicate rows" value={fmt(result.duplicate_rows)} sub="Full-row duplicates" icon={ShieldCheck} tone="green"/></div>
      <div className="dashboard-grid grid-main"><Panel title="Explore a column" sub="Select a field to see its value distribution"><label className="upload-select"><span>Column</span><select value={selected} onChange={e=>setSelected(e.target.value)}>{result.profile.map(item=><option key={item.column} value={item.column}>{item.column} · {item.data_type}</option>)}</select></label>{chartData.length?<BasicBars data={chartData} x="label" y="count"/>:<Empty text="This column has no values to chart."/>}</Panel><Panel title={selectedProfile?.data_type==='numeric'?'Numeric summary':'Column profile'} sub={selectedProfile?.column||'Choose a column'}><DataTable data={selectedProfile?[selectedProfile]:[]} limit={1}/><div className="missing-summary"><span>Missing values in this column</span><b>{fmt(selectedProfile?.missing)} ({fmt(selectedProfile?.missing_pct,'percent')})</b></div></Panel></div>
      <Panel title="Uploaded data preview" sub="First 100 rows from the uploaded file. Values are shown as received."><DataTable data={result.preview} limit={12}/></Panel></>}
  </>;
}

function FilterBar({options,filters,update}) {
  const restaurantOptions=(options?.restaurants||[]).map(item=>({id:item.split(' | ',1)[0],label:item.split(' | ').slice(1).join(' | ')}));
  return <div className="filter-bar"><div className="filter-title"><Filter size={16}/><span>Filters</span></div><label className="filter-control date-filter"><CalendarDays size={15}/><input type="date" min={options?.min_date||undefined} max={options?.max_date||undefined} value={filters.start_date} onChange={e=>update('start_date',e.target.value)}/><span>to</span><input type="date" min={options?.min_date||undefined} max={options?.max_date||undefined} value={filters.end_date} onChange={e=>update('end_date',e.target.value)}/></label><SelectFilter label="City" value={filters.city} options={options?.cities} onChange={v=>update('city',v)}/><SelectFilter label="Restaurant" value={filters.restaurant_id} options={restaurantOptions.map(x=>x.id)} labels={Object.fromEntries(restaurantOptions.map(x=>[x.id,x.label]))} onChange={v=>update('restaurant_id',v)}/><SelectFilter label="Cuisine" value={filters.cuisine} options={options?.cuisines} onChange={v=>update('cuisine',v)}/><SelectFilter label="Payment" value={filters.payment_method} options={options?.payment_methods} onChange={v=>update('payment_method',v)}/><SelectFilter label="Status" value={filters.order_status} options={options?.statuses} onChange={v=>update('order_status',v)}/><button className="reset-filter" onClick={()=>{['start_date','end_date','city','restaurant_id','cuisine','payment_method','order_status'].forEach(k=>update(k,''))}}><X size={14}/> Reset</button></div>;
}
function SelectFilter({label,value,options=[],labels={},onChange}) {return <label className="filter-control select-filter"><span>{label}</span><select value={value} onChange={e=>onChange(e.target.value)}><option value="">All</option>{(options||[]).map(o=><option key={o} value={o}>{labels[o]||o}</option>)}</select><ChevronDown size={13}/></label>}

function MetricCard({label,value,sub,icon:Icon,tone='teal'}) {return <div className="metric-card"><div className="metric-top"><span>{label}</span><div className={`metric-icon ${tone}`}><Icon size={18}/></div></div><strong>{value}</strong><div className="metric-foot"><span className="metric-context">{sub}</span></div></div>}
const TOUR_PANEL_TARGETS={'Order activity calendar':'tour-orders','Try a what-if scenario':'tour-scenario','Restaurant performance quadrant':'tour-restaurants','Delivery time by city and vehicle':'tour-delivery','Order frequency':'tour-customers','City activity map':'tour-cities','Rejected records':'tour-quality','Execution history':'tour-etl','Upload your data':'tour-upload','How it works':'tour-about'};
function Panel({title,sub,action,children,className=''}) {return <section data-tour-id={TOUR_PANEL_TARGETS[title]} className={`panel ${className}`}><div className="panel-heading"><div><h2>{title}</h2>{sub&&<p>{sub}</p>}</div>{action}</div>{children}</section>}
function ChartTip({active,payload,label}) {if(!active||!payload?.length)return null;return <div className="chart-tip"><b>{label}</b>{payload.map((p,i)=><span key={i}><i style={{background:p.color}}/>{p.name}: {typeof p.value==='number'?fmt(p.value):p.value}</span>)}</div>}
function Empty({text='No records match these filters.'}) {return <div className="empty-state"><BarChart3 size={25}/><b>Nothing to show yet</b><span>{text}</span></div>}
function LoadingSkeleton() {return <div className="skeleton-grid"><div/><div/><div/><div/></div>}
function DataTable({data=[],columns,limit=10}) {
  if(!data.length)return <Empty/>;
  const cols=columns||Object.keys(data[0]).filter(k=>!['original_record','transformation_counts','rejection_reason_counts','source_row_counts'].includes(k)).slice(0,8);
  return <div className="table-wrap"><table><thead><tr>{cols.map(c=><th key={c}>{c.replaceAll('_',' ')}</th>)}</tr></thead><tbody>{data.slice(0,limit).map((row,i)=><tr key={i}>{cols.map(c=><td key={c}>{formatCell(row[c],c)}</td>)}</tr>)}</tbody></table>{data.length>limit&&<div className="table-note">Showing {limit} of {fmt(data.length)} rows</div>}</div>;
}
function formatCell(v,key='') {if(v==null)return '—';if(typeof v==='number')return key.includes('revenue')||key.includes('spend')||key.includes('amount')?fmt(v,'money'):key.includes('percentage')||key.includes('rate')?fmt(v,'percent'):Number.isInteger(v)?fmt(v):fmt(v,'decimal');if(typeof v==='object')return JSON.stringify(v);return String(v)}
function downloadRows(data,filename){const cols=Object.keys(data[0]||{});const csv=[cols.join(','),...data.map(row=>cols.map(col=>`"${String(row[col]??'').replaceAll('"','""')}"`).join(','))].join('\n');const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));link.download=filename;link.click();URL.revokeObjectURL(link.href)}
function ExportButton({onClick,label='Export CSV'}) {return <button className="button-secondary" onClick={onClick}><Download size={15}/>{label}</button>}
function StatusBadge({value}) {const x=String(value||'unknown').toLowerCase();return <span className={`status-badge ${x==='succeeded'||x==='delivered'?'good':x==='failed'||x==='cancelled'?'bad':'neutral'}`}>{x}</span>}

function renderPage(page,d,filters,exportCsv,selectPage,onCitySelect) {
  if(page==='Overview')return <Overview d={d} exportCsv={exportCsv} filters={filters} onCitySelect={onCitySelect}/>;
  if(page==='Orders')return <Orders d={d} exportCsv={exportCsv}/>;
  if(page==='Forecast')return <ForecastPage filters={filters} d={d}/>;
  if(page==='Restaurants')return <Restaurants d={d} exportCsv={exportCsv}/>;
  if(page==='Delivery')return <Delivery d={d} exportCsv={exportCsv}/>;
  if(page==='Customers')return <Customers d={d} exportCsv={exportCsv}/>;
  if(page==='Cities')return <Cities d={d} exportCsv={exportCsv} filters={filters} onCitySelect={onCitySelect}/>;
  if(page==='Data Quality')return <Quality d={d} exportCsv={exportCsv}/>;
  if(page==='ETL Monitor')return <ETL d={d}/>;
  if(page==='Upload Analysis')return <UploadAnalysis/>;
  if(page==='Reports')return <Reports exportCsv={exportCsv}/>;
  return <About selectPage={selectPage}/>;
}
function Overview({d,exportCsv,filters,onCitySelect}) {
  const k=rows(d.overall_kpis)[0]||{};const daily=rows(d.daily_advanced_trends);const status=rows(d.order_status_distribution);const top=rows(d.top_restaurants_by_revenue);const cuisine=rows(d.cuisine_analytics);const vehicle=rows(d.vehicle_type_comparison);const cities=rows(d.city_analytics);
  return <>
    <div className="welcome-banner"><div><div className="banner-label"><Zap size={14}/> LIVE OPERATIONS SNAPSHOT</div><h2>Your service at a glance</h2><p>Orders, customer demand and delivery performance—all in one place.</p></div><div className="banner-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="banner-icon"><Utensils size={31}/></div><span className="spark spark-a">✦</span><span className="spark spark-b">✦</span><span className="spark spark-c">·</span></div></div>
    <SectionTitle label="BUSINESS HEALTH" title="Key performance indicators"/>
    <div className="metric-grid"><MetricCard label="Total orders" value={fmt(k.total_orders)} sub="Orders in current selection" icon={ShoppingBag}/><MetricCard label="Completed" value={fmt(k.completed_orders)} sub="Successfully delivered" icon={Check} tone="green"/><MetricCard label="Cancelled" value={fmt(k.cancelled_orders)} sub={`${fmt(k.cancellation_percentage,'percent')} cancellation rate`} icon={X} tone="gold"/><MetricCard label="Revenue" value={fmt(k.total_revenue,'money')} sub="Completed orders only" icon={BarChart3} tone="gold"/></div>
    <div className="metric-grid"><MetricCard label="Average order value" value={fmt(k.average_order_value,'money')} sub="Delivered orders only" icon={ShoppingBag}/><MetricCard label="Avg. delivery time" value={`${fmt(k.average_delivery_time,'decimal')} min`} sub="Pickup to customer" icon={Clock3} tone="violet"/><MetricCard label="Late deliveries" value={fmt(k.late_deliveries)} sub={`${fmt(k.late_delivery_percentage,'percent')} of completed orders`} icon={Activity} tone="gold"/><MetricCard label="Late delivery rate" value={fmt(k.late_delivery_percentage,'percent')} sub="Completed orders only" icon={Clock3} tone="green"/></div>
    <div className="dashboard-grid grid-main"><Panel title="Orders & revenue" sub="Daily trend for selected filters" className="chart-panel"><TrendChart data={daily}/></Panel><Panel title="Order status" sub="Share of validated orders"><StatusDonut data={status}/></Panel></div>
    <Panel title="Order outcome flow" sub="Filtered orders split into their recorded final statuses" className="span-all"><StatusFlow data={status}/></Panel>
    <SectionTitle label="CITY VIEW" title="Delivery activity across India"/>
    <div className="dashboard-grid grid-main map-layout"><Panel title="Orders by city" sub="Select a city marker to filter the whole dashboard"><CityMap data={cities} selectedCity={filters.city} onCitySelect={onCitySelect} height={390}/></Panel><Panel title="A delivery, step by step" sub="Illustrative journey · not a live GPS route"><DeliveryJourney/><div className="city-pulse-title">Busiest cities in this view</div><RankList data={cities} label="city" value="total_orders"/></Panel></div>
    <div className="dashboard-grid grid-bottom"><Panel title="Top restaurants" sub="Ranked by completed order revenue" action={<button className="text-action" onClick={()=>exportCsv('top_restaurants_by_revenue')}>Export <Download size={14}/></button>}><RankList data={top} label="restaurant_name" value="revenue" kind="money"/></Panel><Panel title="Cuisine mix" sub="Order volume by cuisine"><CompactBars data={cuisine} label="cuisine" value="total_orders"/></Panel><Panel title="Delivery modes" sub="Average completed delivery time"><CompactBars data={vehicle} label="vehicle_type" value="average_delivery_time" suffix=" min"/></Panel></div>
  </>;
}
function ForecastPage({filters,d}) {
  const [horizon,setHorizon]=useState(7),[result,setResult]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
  const [scenarioOrders,setScenarioOrders]=useState(''),[scenarioAov,setScenarioAov]=useState('');
  const filterKey=JSON.stringify(filters);
  useEffect(()=>{
    let cancelled=false;setLoading(true);setError('');
    const params=new URLSearchParams({horizon:String(horizon)});
    Object.entries(filters).forEach(([key,value])=>{if(value!==''&&value!=null)params.set(key==='end_date'?'anchor_date':key,value)});
    apiGet(`/api/forecast?${params}`).then(data=>{if(!cancelled)setResult(data)}).catch(e=>{if(!cancelled)setError(e.message)}).finally(()=>{if(!cancelled)setLoading(false)});
    return ()=>{cancelled=true};
  },[filterKey,horizon]);
  if(loading)return <div className="loading-state"><div className="spinner"/><b>Building a demand forecast</b><span>Aggregating filtered PostgreSQL history and checking a holdout window…</span></div>;
  if(error)return <div className="error-banner"><div><b>Forecast unavailable</b><span>{error}</span></div><button onClick={()=>setHorizon(v=>v===7?14:7)}>Retry</button></div>;
  const m=result.metrics,improve=m.mae_improvement_pct,kpi=rows(d?.overall_kpis)[0]||{};
  const baseAov=Number(kpi.average_order_value||0),completionRate=Number(kpi.total_orders)>0?Number(kpi.completed_orders||0)/Number(kpi.total_orders):0;
  const orderInput=scenarioOrders===''?Number(m.forecast_orders):Math.max(0,Number(scenarioOrders)||0);
  const aovInput=scenarioAov===''?baseAov:Math.max(0,Number(scenarioAov)||0);
  const estimatedCompleted=orderInput*completionRate,estimatedRevenue=estimatedCompleted*aovInput;
  return <><div className="forecast-intro"><div><span className="forecast-tag"><TrendingUp size={14}/> DEMAND OUTLOOK</span><h2>{horizon}-day order forecast</h2><p>{filters.city||'All selected cities'} · Based on filtered PostgreSQL orders through {m.anchor_date}.</p></div><div className="segmented-control"><button className={horizon===7?'selected':''} onClick={()=>setHorizon(7)}>7 days</button><button className={horizon===14?'selected':''} onClick={()=>setHorizon(14)}>14 days</button></div></div>
    <div className="forecast-notice"><Activity size={15}/><span>Transparent baseline model: mean of the previous four matching weekdays. Error bands show the 90th-percentile absolute error from a rolling 28-day backtest.</span></div>
    <div className="metric-grid"><MetricCard label={`Forecast orders · next ${horizon} days`} value={fmt(m.forecast_orders)} sub="Sum of daily weekday forecasts" icon={ShoppingBag}/><MetricCard label="Forecast revenue" value={fmt(m.forecast_revenue,'money')} sub="Completed-order revenue estimate" icon={BarChart3} tone="gold"/><MetricCard label="Backtest MAE" value={fmt(m.orders_mae,'decimal')} sub={`Orders per day · ${m.backtest_days} held-out days`} icon={Activity} tone="violet"/><MetricCard label="Vs last-week baseline" value={improve==null?'—':`${improve>=0?'+':''}${fmt(improve,'decimal')}%`} sub={improve==null?'Baseline error unavailable':improve>=0?'Lower backtest error is better':'Higher backtest error than baseline'} icon={improve!=null&&improve>=0?Check:Clock3} tone={improve!=null&&improve>=0?'green':'gold'}/></div>
    <Panel title="Try a what-if scenario" sub="Enter your expected order volume and average basket value. The completion rate comes from the filtered PostgreSQL data.">
      <div className="scenario-form"><label><span>Expected orders over {horizon} days</span><input type="number" min="0" step="1" value={scenarioOrders===''?Math.round(m.forecast_orders):scenarioOrders} onChange={e=>setScenarioOrders(e.target.value)} placeholder="Enter expected order count"/><small>Database forecast: {fmt(m.forecast_orders)} orders</small></label><label><span>Average order value</span><div className="scenario-currency"><b>₹</b><input type="number" min="0" step="10" value={scenarioAov===''?Math.round(baseAov):scenarioAov} onChange={e=>setScenarioAov(e.target.value)} placeholder="Enter basket value"/></div><small>Filtered historical AOV: {fmt(baseAov,'money')}</small></label><button className="button-secondary" onClick={()=>{setScenarioOrders('');setScenarioAov('')}}>Reset to data</button></div>
      <div className="scenario-results"><MetricCard label="Estimated completed orders" value={fmt(estimatedCompleted)} sub={`${fmt(completionRate*100,'percent')} historical completion rate`} icon={Check} tone="green"/><MetricCard label="Estimated revenue" value={fmt(estimatedRevenue,'money')} sub={`${fmt(estimatedCompleted)} completed orders × ${fmt(aovInput,'money')} AOV`} icon={BarChart3} tone="gold"/></div>
      <p className="model-footnote">This is a scenario estimate, not a new database forecast. Update the inputs to explore different operating assumptions.</p>
    </Panel>
    <Panel title="Historical orders and forecast" sub="The forecast starts after the selected end date; shaded band is historical backtest error, not a guarantee." action={<button className="text-action" onClick={()=>downloadRows(result.forecast,'demand_forecast.csv')}>Export forecast <Download size={14}/></button>}><ForecastChart history={result.history} forecast={result.forecast}/></Panel>
    <div className="dashboard-grid grid-main"><Panel title="Forecast details" sub="Daily values and empirical error ranges"><DataTable data={result.forecast} limit={14}/></Panel><Panel title="Backtest comparison" sub="Lower MAE is better"><div className="backtest-score"><span>Weekday mean model</span><b>{fmt(m.orders_mae,'decimal')} orders/day</b><div className="score-track"><i style={{width:`${Math.max(4,Math.min(100,(m.orders_mae/Math.max(m.orders_mae,m.baseline_mae,1))*100))}%`}}/></div></div><div className="backtest-score"><span>Same weekday last week</span><b>{fmt(m.baseline_mae,'decimal')} orders/day</b><div className="score-track baseline"><i style={{width:`${Math.max(4,Math.min(100,(m.baseline_mae/Math.max(m.orders_mae,m.baseline_mae,1))*100))}%`}}/></div></div><p className="model-footnote">Rolling one-day-ahead evaluation over the final 28 historical days. Training window: {m.history_days} days.</p></Panel></div>
  </>;
}
function ForecastChart({history=[],forecast=[]}) {
  const data=[...history.map(x=>({...x,bandBase:null,bandSpan:null})),...forecast.map(x=>({date:x.date,actual_orders:null,predicted_orders:x.predicted_orders,bandBase:x.orders_lower,bandSpan:x.orders_upper-x.orders_lower}))];
  if(!data.length)return <Empty/>;
  return <div className="chart-area forecast-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={data} margin={{top:10,right:12,bottom:0,left:0}}><CartesianGrid stroke="#edf1ef" vertical={false}/><XAxis dataKey="date" tickFormatter={dateLabel} tickLine={false} axisLine={false} minTickGap={22}/><YAxis tickLine={false} axisLine={false}/><Tooltip content={<ChartTip/>}/><Legend/><Area dataKey="bandBase" stackId="uncertainty" fill="transparent" stroke="none" legendType="none" isAnimationActive={false}/><Area dataKey="bandSpan" name="90% historical error band" stackId="uncertainty" fill="#f3a85a" fillOpacity={.2} stroke="none" isAnimationActive={false}/><Line dataKey="actual_orders" name="Actual orders" type="monotone" stroke="#148477" strokeWidth={2.4} dot={false} connectNulls={false}/><Line dataKey="predicted_orders" name="Forecast orders" type="monotone" stroke="#e39a49" strokeWidth={2.5} strokeDasharray="6 4" dot={{r:3,fill:'#e39a49'}} connectNulls={false}/></ComposedChart></ResponsiveContainer></div>;
}
function SectionTitle({label,title}) {return <div className="section-title"><span>{label}</span><h2>{title}</h2></div>}
function TrendChart({data=[]}) {if(!data.length)return <Empty/>;return <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data} margin={{top:15,right:10,left:0,bottom:0}}><defs><linearGradient id="ordersFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#148477" stopOpacity={.2}/><stop offset="100%" stopColor="#148477" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#edf1ef" vertical={false}/><XAxis dataKey="order_date" tickFormatter={dateLabel} tickLine={false} axisLine={false} minTickGap={25}/><YAxis yAxisId="orders" tickLine={false} axisLine={false} width={42}/><YAxis yAxisId="revenue" orientation="right" tickLine={false} axisLine={false} width={55} tickFormatter={v=>`${Math.round(v/1000)}k`}/><Tooltip content={<ChartTip/>}/><Area yAxisId="orders" type="monotone" dataKey="total_orders" name="Orders" stroke="#148477" strokeWidth={2.5} fill="url(#ordersFill)" activeDot={{r:5}}/><Line yAxisId="revenue" type="monotone" dataKey="revenue" name="Revenue (₹)" stroke="#f3a85a" strokeWidth={2} dot={false}/></AreaChart></ResponsiveContainer></div>}
function StatusDonut({data=[]}) {if(!data.length)return <Empty/>;return <div className="donut-layout"><div className="donut-chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={data} dataKey="total_orders" nameKey="order_status" innerRadius="67%" outerRadius="91%" paddingAngle={4} stroke="none">{data.map((_,i)=><Cell key={i} fill={COLORS[i%COLORS.length]}/>)}</Pie><Tooltip formatter={v=>fmt(v)}/></PieChart></ResponsiveContainer><div className="donut-center"><b>{fmt(data.reduce((a,x)=>a+Number(x.total_orders||0),0))}</b><span>ORDERS</span></div></div><div className="legend-list">{data.map((x,i)=><div key={x.order_status}><i style={{background:COLORS[i%COLORS.length]}}/><span>{x.order_status}</span><b>{fmt(x.total_orders)}</b></div>)}</div></div>}
function StatusFlow({data=[]}) {if(!data.length)return <Empty/>;const order=['delivered','cancelled','failed'];const palette={delivered:'#148477',cancelled:'#e69b50',failed:'#9a8eb9'};const rowsByStatus=order.map(status=>data.find(x=>x.order_status===status)).filter(Boolean);const total=rowsByStatus.reduce((sum,x)=>sum+Number(x.total_orders||0),0);const ys=[32,105,178];return <div className="status-flow"><svg viewBox="0 0 620 250" role="img" aria-label="Validated orders flow to their recorded final status">{rowsByStatus.map((row,i)=>{const y=ys[i]+23,count=Number(row.total_orders||0),color=palette[row.order_status]||COLORS[i];return <path key={row.order_status} d={`M 168 125 C 275 125, 320 ${y}, 420 ${y}`} fill="none" stroke={color} strokeOpacity=".48" strokeWidth={Math.max(3,Math.sqrt(count/Math.max(total,1))*62)} strokeLinecap="round"/>})}<rect x="20" y="93" width="150" height="64" rx="13" fill="#eaf3ef"/><text x="35" y="119" className="flow-source-label">VALIDATED ORDERS</text><text x="35" y="142" className="flow-source-count">{fmt(total)}</text>{rowsByStatus.map((row,i)=>{const y=ys[i],count=Number(row.total_orders||0),pct=total?100*count/total:0,color=palette[row.order_status]||COLORS[i];return <g key={row.order_status}><rect x="420" y={y} width="180" height="46" rx="11" fill="#fff" stroke="#e8eeea"/><circle cx="439" cy={y+23} r="5" fill={color}/><text x="452" y={y+20} className="flow-status-label">{row.order_status}</text><text x="452" y={y+34} className="flow-status-share">{fmt(pct,'percent')} of orders</text><text x="584" y={y+28} textAnchor="end" className="flow-status-count">{fmt(count)}</text></g>})}</svg></div>}
function RankList({data=[],label,value,kind='number'}) {if(!data.length)return <Empty/>;const max=Math.max(...data.map(x=>Number(x[value]||0)),1);return <div className="rank-list">{data.slice(0,5).map((x,i)=><div className="rank-row" key={x[label]}><span className="rank-num">{String(i+1).padStart(2,'0')}</span><div className="rank-content"><div><b>{x[label]}</b><strong>{fmt(x[value],kind)}</strong></div><div className="rank-track"><i style={{width:`${Math.max(5,Number(x[value]||0)/max*100)}%`}}/></div></div></div>)}</div>}
function CompactBars({data=[],label,value,suffix=''}) {if(!data.length)return <Empty/>;return <div className="compact-bars">{data.slice(0,5).map((x,i)=><div className="compact-row" key={x[label]}><div><span>{x[label]}</span><b>{fmt(x[value],value.includes('revenue')?'money':'decimal')}{suffix}</b></div><div className="bar-track"><i style={{width:`${Math.max(4,Number(x[value]||0)/Math.max(...data.map(z=>Number(z[value]||0)),1)*100)}%`,background:COLORS[i%COLORS.length]}}/></div></div>)}</div>}

function Orders({d,exportCsv}) {const daily=rows(d.daily_advanced_trends),monthly=rows(d.monthly_advanced_trends),payments=rows(d.orders_by_payment_method),status=rows(d.order_status_distribution),hours=rows(d.peak_ordering_hours),periods=rows(d.weekday_weekend_performance),aov=rows(d.average_order_value_trends),heat=rows(d.orders_by_weekday_hour);return <><div className="metric-grid three"><MetricCard label="Orders in range" value={fmt(daily.reduce((a,x)=>a+Number(x.total_orders||0),0))} sub="By selected dates" icon={ShoppingBag}/><MetricCard label="Revenue" value={fmt(daily.reduce((a,x)=>a+Number(x.revenue||0),0),'money')} sub="Delivered orders" icon={BarChart3} tone="gold"/><MetricCard label="Average order value" value={fmt(rows(d.overall_kpis)[0]?.average_order_value,'money')} sub="Delivered orders only" icon={Activity} tone="violet"/></div><div className="dashboard-grid grid-main"><Panel title="Daily orders" sub="Actual orders and 7-day average"><BasicLine data={daily} x="order_date" y="total_orders" name="Orders"/></Panel><Panel title="Monthly orders" sub="Monthly volume"><BasicBars data={monthly} x="order_month" y="total_orders"/></Panel></div><Panel title="Order activity calendar" sub="Daily volume across the selected date range; darker cells mark busier days"><CalendarHeatmap data={daily}/></Panel><div className="dashboard-grid grid-main"><Panel title="Peak ordering hours" sub="Order volume by hour"><BasicBars data={hours} x="order_hour" y="total_orders"/></Panel><Panel title="Order status" sub="Current filtered status mix"><StatusDonut data={status}/></Panel></div><div className="dashboard-grid grid-main"><Panel title="Payment mix" sub="Order volume by payment method"><CompactBars data={payments} label="payment_method" value="total_orders"/></Panel><Panel title="Weekday vs weekend" sub="Orders and revenue by day type"><CompactBars data={periods} label="period" value="total_orders"/></Panel></div><div className="dashboard-grid grid-main"><Panel title="Average order value" sub="Daily completed order value"><BasicLine data={aov} x="order_date" y="average_order_value" name="AOV" money/></Panel><Panel title="Ordering rhythm" sub="Orders by weekday and hour"><WeekHourGrid data={heat}/></Panel></div><ExportButton onClick={()=>exportCsv('filtered_orders')}/></>}
function BasicLine({data=[],x,y,name='Value',money=false}) {if(!data.length)return <Empty/>;return <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><LineChart data={data}><CartesianGrid stroke="#edf1ef" vertical={false}/><XAxis dataKey={x} tickFormatter={x.includes('date')?dateLabel:undefined} tickLine={false} axisLine={false}/><YAxis tickLine={false} axisLine={false} tickFormatter={money?v=>`${Math.round(v/1000)}k`:undefined}/><Tooltip content={<ChartTip/>}/><Line type="monotone" dataKey={y} name={name} stroke="#148477" strokeWidth={2.5} dot={false} activeDot={{r:5}}/></LineChart></ResponsiveContainer></div>}
function BasicBars({data=[],x,y}) {if(!data.length)return <Empty/>;return <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} margin={{top:8,right:8,left:0,bottom:3}}><CartesianGrid stroke="#edf1ef" vertical={false}/><XAxis dataKey={x} tickLine={false} axisLine={false} tickFormatter={x==='order_date'?dateLabel:undefined}/><YAxis tickLine={false} axisLine={false}/><Tooltip content={<ChartTip/>}/><Bar dataKey={y} name={y.replaceAll('_',' ')} fill="#148477" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div>}
function WeekHourGrid({data=[]}) {if(!data.length)return <Empty/>;const max=Math.max(...data.map(x=>Number(x.total_orders||0)),1);const days=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];return <div className="heat-grid"><div className="heat-corner"/>{Array.from({length:24},(_,h)=><span className="heat-hour" key={h}>{h%3===0?h:''}</span>)}{days.map((day,i)=><React.Fragment key={day}><span className="heat-day">{day}</span>{Array.from({length:24},(_,h)=>{const n=Number(data.find(x=>Number(x.weekday)===i+1&&Number(x.order_hour)===h)?.total_orders||0);return <i key={h} title={`${day} ${h}:00 · ${n} orders`} style={{background:n?`rgba(20,132,119,${.1+.85*n/max})`:'#f0f4f1'}}/>})}</React.Fragment>)}</div>}
function CalendarHeatmap({data=[]}) {if(!data.length)return <Empty/>;const sorted=[...data].sort((a,b)=>a.order_date.localeCompare(b.order_date)),start=new Date(`${sorted[0].order_date}T12:00:00`),offset=(start.getDay()+6)%7,total=offset+sorted.length,weeks=Math.ceil(total/7),max=Math.max(...sorted.map(x=>Number(x.total_orders||0)),1),values=new Map(sorted.map(x=>[x.order_date,Number(x.total_orders||0)])),weekLabels=Array(weeks).fill('');sorted.forEach(row=>{const date=new Date(`${row.order_date}T12:00:00`);if(date.getDate()<=7){const idx=Math.floor((offset+Math.round((date-start)/86400000))/7);weekLabels[idx]=date.toLocaleDateString('en-IN',{month:'short'})}});const cols=`30px repeat(${weeks},12px)`;return <div className="calendar-heat-wrap"><div className="calendar-heat" style={{gridTemplateColumns:cols}}><span/>{weekLabels.map((m,i)=><small key={i}>{m}</small>)}{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((day,weekday)=><React.Fragment key={day}><span className="calendar-day">{day}</span>{Array.from({length:weeks},(_,week)=>{const idx=week*7+weekday-offset,row=sorted[idx],count=row?values.get(row.order_date):null,alpha=count==null?0:Math.max(.12,.12+.82*count/max);return <i key={week} title={row?`${row.order_date} · ${fmt(count)} orders`:'No date in range'} style={{background:count==null?'transparent':`rgba(20,132,119,${alpha})`}}/>})}</React.Fragment>)}</div><div className="calendar-legend"><span>Fewer orders</span>{[.12,.3,.5,.72,.94].map((alpha,i)=><i key={i} style={{background:`rgba(20,132,119,${alpha})`}}/>)}<span>More orders</span></div></div>}
function DeliveryJourney() {return <div className="journey-card"><div className="journey-track"><div className="journey-node"><Store size={17}/></div><div className="journey-dash"/><div className="journey-rider"><Bike size={22}/></div><div className="journey-node"><Users size={17}/></div></div><div className="journey-labels"><span><b>Restaurant</b><small>Order prepared</small></span><span><b>Delivery partner</b><small>On the way</small></span><span><b>Customer</b><small>Delivered</small></span></div><div className="journey-foot"><span className="journey-live-dot"/>Order handoff flow <em>Illustrative animation</em></div></div>}

function Restaurants({d,exportCsv}) {const revenue=rows(d.top_restaurants_by_revenue),orders=rows(d.top_restaurants_by_orders),ratings=rows(d.restaurant_ratings),cuisine=rows(d.cuisine_analytics);return <><div className="dashboard-grid grid-main"><Panel title="Revenue leaders" sub="Restaurants ranked by revenue"><RankList data={revenue} label="restaurant_name" value="revenue" kind="money"/></Panel><Panel title="Order volume leaders" sub="Restaurants ranked by number of orders"><RankList data={orders} label="restaurant_name" value="total_orders"/></Panel></div><div className="dashboard-grid grid-main"><Panel title="Cuisine revenue" sub="Delivered order revenue by cuisine"><CompactBars data={cuisine} label="cuisine" value="revenue"/></Panel><Panel title="Orders by cuisine" sub="Order mix across cuisines"><CompactBars data={cuisine} label="cuisine" value="total_orders"/></Panel></div><Panel title="Restaurant performance quadrant" sub="Rating vs delivered revenue; bubble size represents order count"><RestaurantQuadrant data={ratings}/></Panel><Panel title="Restaurant performance" sub="Rating, preparation time and delivery reliability" action={<ExportButton onClick={()=>exportCsv('restaurant_ratings')}/> }><DataTable data={ratings} limit={15}/></Panel></>}
function median(values) {const sorted=values.filter(Number.isFinite).sort((a,b)=>a-b);if(!sorted.length)return 0;const mid=Math.floor(sorted.length/2);return sorted.length%2?sorted[mid]:(sorted[mid-1]+sorted[mid])/2}
function RestaurantQuadrant({data=[]}) {if(!data.length)return <Empty/>;const midRating=median(data.map(x=>Number(x.restaurant_rating))),midRevenue=median(data.map(x=>Number(x.revenue)));return <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{top:12,right:22,bottom:15,left:12}}><CartesianGrid stroke="#edf1ef"/><XAxis type="number" dataKey="restaurant_rating" name="Rating" domain={[0,5]} tickLine={false} axisLine={false} label={{value:'Restaurant rating / 5',position:'insideBottom',offset:-7,fontSize:9}}/><YAxis type="number" dataKey="revenue" name="Revenue" tickLine={false} axisLine={false} tickFormatter={v=>`${Math.round(v/1000)}k`} label={{value:'Revenue (₹)',angle:-90,position:'insideLeft',fontSize:9}}/><ZAxis type="number" dataKey="total_orders" range={[45,420]} name="Orders"/><ReferenceLine x={midRating} stroke="#9daea5" strokeDasharray="4 4"/><ReferenceLine y={midRevenue} stroke="#9daea5" strokeDasharray="4 4"/><Tooltip content={<RestaurantQuadrantTip/>}/><Scatter name="Restaurants" data={data} fill="#148477" fillOpacity={.68}/></ScatterChart></ResponsiveContainer></div>}
function RestaurantQuadrantTip({active,payload}) {const r=payload?.[0]?.payload;if(!active||!r)return null;return <div className="chart-tip"><b>{r.restaurant_name}</b><span>Rating: {fmt(r.restaurant_rating,'decimal')} / 5</span><span>Revenue: {fmt(r.revenue,'money')}</span><span>Orders: {fmt(r.total_orders)}</span></div>}
function Delivery({d,exportCsv}) {const k=rows(d.overall_kpis)[0]||{},partners=rows(d.delivery_partner_analytics),vehicles=rows(d.vehicle_type_comparison),cityVehicles=rows(d.city_vehicle_delivery),dist=rows(d.delivery_time_distribution),cities=rows(d.city_analytics),scatter=rows(d.delivery_distance_scatter);return <><div className="metric-grid three"><MetricCard label="Average delivery" value={`${fmt(k.average_delivery_time,'decimal')} min`} sub="Pickup to drop-off" icon={Clock3}/><MetricCard label="Late deliveries" value={fmt(k.late_deliveries)} sub={`${fmt(k.late_delivery_percentage,'percent')} of completed orders`} icon={Activity} tone="gold"/><MetricCard label="Delivery partners" value={fmt(partners.length)} sub="In selected data" icon={Bike} tone="violet"/></div><div className="dashboard-grid grid-main"><Panel title="Delivery time distribution" sub="Completed orders by time range"><BasicBars data={dist} x="bucket" y="deliveries"/></Panel><Panel title="Vehicle comparison" sub="Average delivery time by vehicle"><CompactBars data={vehicles} label="vehicle_type" value="average_delivery_time" suffix=" min"/></Panel></div><Panel title="Delivery time by city and vehicle" sub="Compare mean completed-order time across city and vehicle groups"><DeliveryCityVehicleChart data={cityVehicles}/></Panel><div className="dashboard-grid grid-main"><Panel title="Performance by city" sub="Average delivery time across cities"><CompactBars data={cities} label="city" value="average_delivery_time" suffix=" min"/></Panel><Panel title="Delivery partners" sub="Most completed deliveries"><RankList data={partners} label="partner_name" value="total_deliveries"/></Panel></div><Panel title="Partner scorecard" sub="Delivery time, distance and lateness" action={<ExportButton onClick={()=>exportCsv('delivery_partner_analytics')}/> }><DataTable data={partners} limit={20}/></Panel><Panel title="Distance and delivery time" sub="Each point is a completed order, queried from PostgreSQL"><DeliveryScatter data={scatter}/></Panel></>}
function DeliveryCityVehicleChart({data=[]}) {if(!data.length)return <Empty/>;const vehicles=[...new Set(data.map(x=>x.vehicle_type))],cities=[...new Set(data.map(x=>x.city))],wide=cities.map(city=>{const row={city};data.filter(x=>x.city===city).forEach(x=>row[x.vehicle_type]=Number(x.average_delivery_time||0));return row});return <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={wide} margin={{top:8,right:15,bottom:5,left:0}}><CartesianGrid stroke="#edf1ef" vertical={false}/><XAxis dataKey="city" tickLine={false} axisLine={false}/><YAxis tickLine={false} axisLine={false} unit=" min"/><Tooltip formatter={value=>`${Number(value).toFixed(1)} min`}/><Legend/>{vehicles.map((vehicle,i)=><Bar key={vehicle} dataKey={vehicle} name={vehicle} fill={COLORS[i%COLORS.length]} radius={[4,4,0,0]}/>)}</BarChart></ResponsiveContainer></div>}
function DeliveryScatter({data=[]}) {if(!data.length)return <Empty/>;return <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{top:10,right:20,bottom:5,left:0}}><CartesianGrid stroke="#edf1ef"/><XAxis type="number" dataKey="delivery_distance_km" name="Distance (km)" tickLine={false} axisLine={false} label={{value:'Distance (km)',position:'insideBottom',offset:-2,fontSize:9}}/><YAxis type="number" dataKey="delivery_time_minutes" name="Delivery time (min)" tickLine={false} axisLine={false} label={{value:'Minutes',angle:-90,position:'insideLeft',fontSize:9}}/><Tooltip cursor={{strokeDasharray:'3 3'}} content={<ChartTip/>}/><Scatter name="Orders" data={data} fill="#148477" fillOpacity={.62}/></ScatterChart></ResponsiveContainer></div>}
function Customers({d,exportCsv}) {const k=rows(d.customer_kpis)[0]||{},freq=rows(d.customer_frequency),spend=rows(d.customer_spending_distribution),top=rows(d.top_customers_by_spend);return <><div className="metric-grid three"><MetricCard label="Unique customers" value={fmt(k.unique_customers)} sub="Customers in selected range" icon={Users}/><MetricCard label="Repeat customers" value={fmt(k.repeat_customers)} sub="Two or more validated orders" icon={Activity} tone="green"/><MetricCard label="Orders per customer" value={fmt(k.average_orders_per_customer,'decimal')} sub="All valid orders in range" icon={BarChart3} tone="gold"/></div><div className="dashboard-grid grid-main"><Panel title="Order frequency" sub="Customers by validated order count"><CompactBars data={freq} label="total_orders" value="customers"/></Panel><Panel title="Customer spending" sub="Completed-order spend buckets"><BasicBars data={spend} x="spending_bucket" y="customers"/></Panel></div><Panel title="Highest spending customers" sub="Completed order spending" action={<ExportButton onClick={()=>exportCsv('top_customers_by_spend')}/> }><DataTable data={top} limit={20}/></Panel></>}
function Cities({d,exportCsv,filters,onCitySelect}) {const cities=rows(d.city_analytics);return <><div className="metric-grid three"><MetricCard label="Cities" value={fmt(cities.length)} sub="In current selection" icon={MapPin}/><MetricCard label="Orders" value={fmt(cities.reduce((a,x)=>a+Number(x.total_orders||0),0))} sub="Across selected cities" icon={ShoppingBag} tone="green"/><MetricCard label="Revenue" value={fmt(cities.reduce((a,x)=>a+Number(x.revenue||0),0),'money')} sub="Delivered order revenue" icon={BarChart3} tone="gold"/></div><Panel title="City activity map" sub="City-centre markers are sized by filtered order volume. Click a marker to select that city."><CityMap data={cities} selectedCity={filters.city} onCitySelect={onCitySelect} height={460}/></Panel><div className="dashboard-grid grid-main"><Panel title="Order volume by city" sub="Compare demand"><CompactBars data={cities} label="city" value="total_orders"/></Panel><Panel title="Revenue by city" sub="Completed order revenue"><CompactBars data={cities} label="city" value="revenue"/></Panel></div><div className="dashboard-grid grid-main"><Panel title="Average delivery time" sub="Completed orders in minutes"><CompactBars data={cities} label="city" value="average_delivery_time" suffix=" min"/></Panel><Panel title="Cancellation rate" sub="Cancelled orders divided by city order volume"><CompactBars data={cities} label="city" value="cancellation_rate" suffix="%"/></Panel></div><Panel title="City performance report" sub="Delivery and cancellation outcomes" action={<ExportButton onClick={()=>exportCsv('city_analytics')}/> }><DataTable data={cities} limit={30}/></Panel></>}
function Quality({d,exportCsv}) {const run=rows(d.latest_quality_run)[0]||{},runs=rows(d.latest_etl_runs),rejected=rows(d.rejected_records),reasonData=run.rejection_reason_counts||{},source=Number(run.source_orders||0),accepted=Number(run.valid_row_count||0);const reasons=Object.entries(reasonData).map(([reason,count])=>({reason,count:Number(count)})).sort((a,b)=>b.count-a.count);return <><div className="metric-grid"><MetricCard label="Source records" value={fmt(source)} sub="Latest audited input" icon={Database}/><MetricCard label="Accepted records" value={fmt(accepted)} sub="Loaded into processed orders" icon={Check} tone="green"/><MetricCard label="Rejected records" value={fmt(run.rejected_row_count)} sub="Held separately for review" icon={ShieldCheck} tone="gold"/><MetricCard label="Acceptance rate" value={fmt(source?accepted/source*100:0,'percent')} sub="Accepted ÷ source rows" icon={Activity} tone="violet"/></div><div className="dashboard-grid grid-main"><Panel title="Rejection reasons" sub="Validation issue counts"><CompactBars data={reasons} label="reason" value="count"/></Panel><Panel title="Latest data quality run" sub="Audit details from PostgreSQL"><DataTable data={run.execution_id?[run]:[]} limit={1}/></Panel></div><Panel title="Rejected records" sub="Records from the latest ETL run" action={run.execution_id&&<ExportButton onClick={()=>exportCsv('rejected_records',{execution_id:run.execution_id})}/> }><DataTable data={rejected} limit={20}/></Panel><Panel title="Recent pipeline executions" sub="Latest ETL audit history"><DataTable data={runs} limit={12}/></Panel></>}
function ETL({d}) {const runs=rows(d.latest_etl_runs),latest=runs[0]||{};return <><div className="run-highlight"><div className="run-icon"><Activity/></div><div><small>LATEST EXECUTION</small><h2>{latest.execution_status||'No runs found'}</h2><p>{latest.execution_timestamp?new Date(latest.execution_timestamp).toLocaleString():'Run the ETL pipeline to begin monitoring.'}</p></div><StatusBadge value={latest.execution_status}/></div><div className="metric-grid three"><MetricCard label="Input records" value={fmt(latest.source_row_counts?.orders)} sub="From latest audit" icon={Database}/><MetricCard label="Processed" value={fmt(latest.valid_row_count)} sub="Accepted and transformed" icon={Check} tone="green"/><MetricCard label="Rejected" value={fmt(latest.rejected_row_count)} sub="Unique records excluded" icon={ShieldCheck} tone="gold"/></div><Panel title="Execution history" sub="Database ETL audit log"><DataTable data={runs} limit={20}/></Panel></>}
function Reports({exportCsv}) {const reports=[['Filtered order detail','filtered_orders','Order records matching the current filters.'],['Restaurant scorecard','restaurant_ratings','Revenue, rating and preparation performance.'],['Delivery partner scorecard','delivery_partner_analytics','Delivery time, distance and late rates.'],['City performance','city_analytics','Order volume, revenue and cancellation by city.'],['Top customer spend','top_customers_by_spend','Completed order customer spend.']];return <><SectionTitle label="DOWNLOAD CENTER" title="Live database reports"/><div className="report-grid">{reports.map(([title,key,desc])=><div className="report-card" key={key}><div className="report-icon"><FileBarChart2 size={19}/></div><h3>{title}</h3><p>{desc}</p><button className="button-primary" onClick={()=>exportCsv(key)}><Download size={15}/> Download CSV</button></div>)}</div><div className="note-card"><Database size={17}/><span>Every export is queried from PostgreSQL using the active global filters.</span></div></>}
function About({selectPage}) {return <><div className="about-hero"><div className="about-icon"><Utensils size={28}/></div><div><span>THE PLATFORM</span><h2>From delivery data to confident decisions.</h2><p>A PostgreSQL-backed analytics workspace for understanding food delivery operations.</p></div></div><Panel title="How it works" sub="A transparent path from source records to useful analytics" className="flow-panel"><div className="flow-steps">{[['01','Source files','Orders and reference data enter the pipeline.'],['02','Validate & transform','ETL verifies records, enriches order facts and preserves rejects.'],['03','PostgreSQL','Accepted records, aggregates and audit history live in the database.'],['04','Explore insights','Interactive filters and SQL-driven analytics reveal performance.']].map(([n,t,c],i)=><div className="flow-step" key={n}><div className="flow-node"><span>{n}</span>{i<3&&<i/>}</div><div><b>{t}</b><p>{c}</p></div></div>)}</div></Panel><SectionTitle label="EXPLORE" title="Pick up where you need insight"/><div className="shortcut-grid">{[['Orders',ShoppingBag,'Trace demand and order patterns.'],['Restaurants',Store,'See which restaurants drive performance.'],['Delivery',Bike,'Understand delivery speed and reliability.'],['Data Quality',ShieldCheck,'Review ETL quality and rejected records.']].map(([name,Icon,desc])=><button className="shortcut-card" key={name} onClick={()=>selectPage(name)}><Icon size={18}/><b>{name}</b><span>{desc}</span><ArrowUpRight size={16}/></button>)}</div></>}

function main() { createRoot(document.getElementById('root')).render(<App/>); }
main();
