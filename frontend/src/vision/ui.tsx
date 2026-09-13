import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { ArrowUpRight, ChevronRight } from 'lucide-react';

export function useStoredState<T>(key: string, initial: T): [T, (next: T | ((previous:T) => T)) => void] {
  const [value, setValue] = useState<T>(() => { try { const saved = localStorage.getItem(`astra-vision:${key}`); return saved ? JSON.parse(saved) as T : initial; } catch { return initial; } });
  useEffect(() => { try { localStorage.setItem(`astra-vision:${key}`, JSON.stringify(value)); } catch { /* Prototype remains usable without browser persistence. */ } }, [key, value]);
  return [value, setValue];
}
export function SectionHeader({eyebrow, title, description, actions}: {eyebrow:string; title:string; description?:string; actions?:ReactNode}) {
  return <header className="section-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description && <p className="section-description">{description}</p>}</div>{actions && <div className="section-actions">{actions}</div>}</header>;
}
export function TextLink({children, onClick}: {children:ReactNode; onClick:()=>void}) { return <button className="text-link" onClick={onClick}>{children}<ArrowUpRight size={15}/></button>; }
export function Tabs<T extends string>({items, value, onChange, label='View'}: {items:readonly {id:T; label:string}[]; value:T; onChange:(value:T)=>void; label?:string}) {
  return <div className="tabs" role="tablist" aria-label={label}>{items.map(item=><button key={item.id} role="tab" aria-selected={value===item.id} onClick={()=>onChange(item.id)}>{item.label}</button>)}</div>;
}
export function DetailRow({label, children}: {label:string; children:ReactNode}) {return <div className="detail-row"><span>{label}</span><span>{children}</span></div>;}
export function Status({children, tone='neutral'}: {children:ReactNode; tone?:'neutral'|'green'|'amber'|'blue'|'red'}) {return <span className={`status status-${tone}`}><i/>{children}</span>;}
export function Breadcrumb({children, onClick}: {children:ReactNode; onClick:()=>void}) {return <button className="breadcrumb" onClick={onClick}>{children}<ChevronRight size={13}/></button>;}
