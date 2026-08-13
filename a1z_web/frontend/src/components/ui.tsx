import type { ButtonHTMLAttributes, PropsWithChildren, ReactNode } from 'react'

export function GlassCard({ children, className = '' }: PropsWithChildren<{ className?: string }>) {
  return <section className={`glass-card ${className}`}>{children}</section>
}

export function Button({ className = '', variant = 'primary', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' }) {
  return <button className={`button button-${variant} ${className}`} {...props} />
}

export function StatusDot({ state = 'unknown', label }: { state?: string; label: string }) {
  return <span className="status"><i className={`dot dot-${state}`} />{label}</span>
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
}

export function PageTitle({ title, description }: { title: string; description: string }) {
  return <div className="page-title"><div><h1>{title}</h1><p>{description}</p></div></div>
}

export function ErrorNotice({ error }: { error: Error | null }) {
  if (!error) return null
  return <div className="notice notice-error" role="alert">{error.message}</div>
}

export function Segmented({ value, onChange }: { value: 'single' | 'dual'; onChange: (value: 'single' | 'dual') => void }) {
  return <div className="segmented" aria-label="机械臂模式">
    {(['single', 'dual'] as const).map((item) => <button type="button" className={value === item ? 'active' : ''} onClick={() => onChange(item)} key={item}>{item === 'dual' ? 'Dual 双臂' : 'Single 单臂'}</button>)}
  </div>
}
