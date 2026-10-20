import type { Section } from "../types";
import { MOBILE_NAV_ITEMS } from "../navigation";

interface MobileNavProps {
  section: Section;
  onSelectSection: (section: Section) => void;
}

export function MobileNav({ section, onSelectSection }: MobileNavProps) {
  return (
    <nav className="mobile-nav">
      {MOBILE_NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <button
            key={item.id}
            className={`mobile-nav-item${section === item.id ? " active" : ""}`}
            onClick={() => onSelectSection(item.id)}
          >
            <Icon size={20} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
