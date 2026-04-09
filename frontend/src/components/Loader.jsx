import PropTypes from "prop-types";

function Loader({ message = "Loading..." }) {
  return (
    <div className="loader">
      <div className="loader-spinner" />
      <p className="loader-text">{message}</p>
    </div>
  );
}

Loader.propTypes = {
  message: PropTypes.string,
};

export default Loader;
