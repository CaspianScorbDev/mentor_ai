import { Menu } from "lucide-react";

interface MobileHeaderProps {
  title: string;
  initials: string;
  onOpenMenu: () => void;
}

export function MobileHeader({ title, initials, onOpenMenu }: MobileHeaderProps) {
  return (
    <header className="mobile-header">
      <button className="icon-btn" title="Меню" onClick={onOpenMenu}>
        <Menu size={20} />
      </button>
      <span className="mobile-title">{title}</span>
      <span className="avatar mobile-avatar">{initials}</span>
    </header>
  );
}
