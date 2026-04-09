function Loader({ message = "Loading..." }) {
  return (
    <div className="loader">
      <div className="loader-spinner" />
      <p className="loader-text">{message}</p>
    </div>
  );
}

export default Loader;
