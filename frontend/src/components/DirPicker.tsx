import Input from './ui/Input'

interface DirPickerProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

export default function DirPicker({ value, onChange, placeholder }: DirPickerProps) {
  return (
    <Input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder ?? '导出目录'}
    />
  )
}
