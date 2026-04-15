import './ErrorMessage.css';

export default function ErrorMessage({ message, onClose }) {
  if (!message) return null;
  return (
    <div className="error-message">
      <span className="error-message-text">{message}</span>
      {onClose && (
        <button className="error-message-close" onClick={onClose}>×</button>
      )}
    </div>
  );
}
