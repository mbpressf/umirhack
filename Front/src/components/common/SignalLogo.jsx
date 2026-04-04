import { useId } from "react";

function Emblem({ small = false }) {
  const size = small ? 32 : 40;
  const clipId = useId();
  const glossId = useId();

  return (
    <svg
      className="signal-emblem"
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <clipPath id={clipId}>
          <circle cx="24" cy="24" r="17.6" />
        </clipPath>
        <linearGradient id={glossId} x1="24" y1="6.4" x2="24" y2="41.6" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#FFFFFF" />
          <stop offset="1" stopColor="#DCE8F8" />
        </linearGradient>
      </defs>

      <circle cx="24" cy="24" r="22" fill="#F4F8FD" stroke="#93AFCF" strokeWidth="1.6" />

      <g clipPath={`url(#${clipId})`}>
        <rect x="6.4" y="6.4" width="35.2" height="11.8" fill="#FFFFFF" />
        <rect x="6.4" y="18.2" width="35.2" height="11.8" fill="#0F4FA8" />
        <rect x="6.4" y="30" width="35.2" height="11.8" fill="#BE3D40" />
        <rect x="6.4" y="6.4" width="35.2" height="35.2" fill={`url(#${glossId})`} opacity="0.22" />

        <circle cx="24" cy="24" r="12.2" fill="#F7FBFF" fillOpacity="0.94" stroke="#A8C1DD" strokeWidth="1.1" />

        <path
          d="M24 12.8 33.2 16.7v8c0 5.6-4 10.2-9.2 12.1-5.2-1.9-9.2-6.5-9.2-12.1v-8z"
          fill="#EFF6FF"
          stroke="#557EA9"
          strokeWidth="1.25"
          strokeLinejoin="round"
        />

      </g>

      <circle cx="24" cy="24" r="17.6" stroke="#C7D7E8" strokeWidth="0.95" />
    </svg>
  );
}

export default function SignalLogo({ compact = false, showSub = true }) {
  return (
    <div className={`signal-logo ${compact ? "compact" : ""}`}>
      <Emblem small={compact} />
      <div className="signal-logo-text">
        <strong>Сигнал</strong>
        {showSub && <span>Объективная аналитика региона</span>}
      </div>
    </div>
  );
}
