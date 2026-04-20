import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import ReferencePage from "./ReferencePage";
import "./index.css";

type ReferenceDetails = {
  title: string;
  filename?: string;
};

function getReferenceDetails(): ReferenceDetails | null {
  const hash = window.location.hash;
  if (!hash.startsWith("#reference")) return null;
  const queryIndex = hash.indexOf("?");
  const queryString = queryIndex >= 0 ? hash.slice(queryIndex + 1) : "";
  const params = new URLSearchParams(queryString);
  const title = params.get("title");

  if (title === null) {
    return null;
  }

  const filename = params.get("filename");
  return {
    title,
    filename: filename === null ? undefined : filename,
  };
}

function Root() {
  const [referenceDetails, setReferenceDetails] = React.useState<ReferenceDetails | null>(
    getReferenceDetails()
  );

  React.useEffect(() => {
    const onHashChange = () => setReferenceDetails(getReferenceDetails());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  if (referenceDetails !== null) {
    return <ReferencePage title={referenceDetails.title} filename={referenceDetails.filename} />;
  }

  return <App />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
