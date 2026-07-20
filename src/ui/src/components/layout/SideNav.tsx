/** App side navigation — Aetheric Voyage shell. */

export type AppNavId = "new-trip" | "recent" | "saved" | "settings";

export interface SideNavProps {
  active: AppNavId;
  onNavigate?: (id: AppNavId) => void;
}

const NAV_ITEMS: { id: AppNavId; label: string; icon: string }[] = [
  { id: "new-trip", label: "New Trip", icon: "add_circle" },
  { id: "recent", label: "Recent Trips", icon: "history" },
  { id: "saved", label: "Saved Itineraries", icon: "bookmark" },
  { id: "settings", label: "Settings", icon: "settings" },
];

export function SideNav({ active, onNavigate }: SideNavProps) {
  return (
    <aside className="side-nav" aria-label="Primary">
      <div className="side-nav__brand">
        <h1 className="side-nav__title">Aether Travel</h1>
        <p className="side-nav__tagline">Premium AI Planning</p>
      </div>

      <nav className="side-nav__nav">
        {NAV_ITEMS.map((item) => {
          const isActive = item.id === active;
          return (
            <button
              key={item.id}
              type="button"
              className={["side-nav__item", isActive ? "side-nav__item--active" : ""]
                .filter(Boolean)
                .join(" ")}
              aria-current={isActive ? "page" : undefined}
              onClick={() => onNavigate?.(item.id)}
            >
              <span className="material-symbols-outlined" aria-hidden="true">
                {item.icon}
              </span>
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="side-nav__footer">
        <button type="button" className="side-nav__upgrade">
          Upgrade to Pro
        </button>
        <div className="side-nav__user">
          <div className="side-nav__avatar" aria-hidden="true">
            AS
          </div>
          <div className="side-nav__user-meta">
            <p className="side-nav__user-name">Alex Sterling</p>
            <p className="side-nav__user-level">Voyager Level</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
