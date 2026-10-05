import { ScanPage } from "./ScanPage";
import { ShelfPage } from "./ShelfPage";
import { ShelvesPage } from "./ShelvesPage";
import { href, useRoute } from "./route";

export function App() {
  // focus moves to the new page's heading on navigation, not on first load
  const { route, navigated } = useRoute();
  const historyCurrent = route.page === "shelves" ? "page" : route.page === "shelf" ? "true" : undefined;

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header>
        <h1>Lacuna</h1>
        <p>Upload a shelf photo to find where product is missing.</p>
        <nav aria-label="Main">
          <ul>
            <li>
              <a href={href.scan} aria-current={route.page === "scan" ? "page" : undefined}>
                Scan a shelf
              </a>
            </li>
            <li>
              <a href={href.shelves} aria-current={historyCurrent}>
                Shelf history
              </a>
            </li>
          </ul>
        </nav>
      </header>
      <main id="main">
        {route.page === "scan" && <ScanPage />}
        {route.page === "shelves" && <ShelvesPage focus={navigated} />}
        {route.page === "shelf" && <ShelfPage key={route.shelf} shelf={route.shelf} focus={navigated} />}
      </main>
      <footer>
        <p>
          Product detection by a YOLO11 model trained on SKU-110K.{" "}
          <a href="https://github.com/ianmcchristian/lacuna">Source on GitHub</a>
        </p>
      </footer>
    </>
  );
}
