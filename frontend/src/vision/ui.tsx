import type { ReactNode } from 'react';
import { useRef } from 'react';
import { ArrowUpRight, ChevronRight } from 'lucide-react';

export function SectionHeader({eyebrow, title, description, actions}: {eyebrow:string; title:string; description?:string; actions?:ReactNode}) {
  return <header className="section-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description && <p className="section-description">{description}</p>}</div>{actions && <div className="section-actions">{actions}</div>}</header>;
}
export function TextLink({children, onClick}: {children:ReactNode; onClick:()=>void}) { return <button className="text-link" onClick={onClick}>{children}<ArrowUpRight size={15}/></button>; }
export function Tabs<T extends string>({items, value, onChange, label='View'}: {items:readonly {id:T; label:string}[]; value:T; onChange:(value:T)=>void; label?:string}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedIndex = Math.max(0, items.findIndex((item) => item.id === value));
  const moveFocus = (index: number) => {
    const next = (index + items.length) % items.length;
    onChange(items[next].id);
    refs.current[next]?.focus();
  };
  return <div className="tabs" role="tablist" aria-orientation="horizontal" aria-label={label}>{items.map((item, index)=><button key={item.id} type="button" role="tab" aria-selected={value===item.id} tabIndex={index===selectedIndex?0:-1} ref={(element) => { refs.current[index] = element; }} onKeyDown={(event) => {
    if (event.key === 'ArrowRight') { event.preventDefault(); moveFocus(index + 1); }
    else if (event.key === 'ArrowLeft') { event.preventDefault(); moveFocus(index - 1); }
    else if (event.key === 'Home') { event.preventDefault(); moveFocus(0); }
    else if (event.key === 'End') { event.preventDefault(); moveFocus(items.length - 1); }
  }} onClick={()=>onChange(item.id)}>{item.label}</button>)}</div>;
}
export function DetailRow({label, children}: {label:string; children:ReactNode}) {return <div className="detail-row"><span>{label}</span><span>{children}</span></div>;}
export function Status({children, tone='neutral'}: {children:ReactNode; tone?:'neutral'|'green'|'amber'|'blue'|'red'}) {return <span className={`status status-${tone}`}><i/>{children}</span>;}
export function Breadcrumb({children, onClick}: {children:ReactNode; onClick:()=>void}) {return <button className="breadcrumb" onClick={onClick}>{children}<ChevronRight size={13}/></button>;}
