import './Loading.css';

export default function Loading({ text = '加载中...' }) {
  return (
    <div className="loading-container">
      <div className="loading-spinner" />
      <span className="loading-text">{text}</span>
    </div>
  );
}
