import { render, screen } from "@testing-library/react";
import { useRef } from "react";
import { useInView } from "./useInView";

function Probe() {
  const ref = useRef<HTMLDivElement>(null);
  const seen = useInView(ref);
  return <div ref={ref}>{seen ? "visible" : "pas encore"}</div>;
}

test("vrai une fois l'élément entré dans l'écran", () => {
  render(<Probe />);
  expect(screen.getByText("visible")).toBeInTheDocument();
});

test("faux tant que l'élément n'est pas visible", () => {
  const original = window.IntersectionObserver;
  window.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } } as never;
  try {
    render(<Probe />);
    expect(screen.getByText("pas encore")).toBeInTheDocument();
  } finally {
    window.IntersectionObserver = original;
  }
});
