import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "@/app/page";

describe("Home page", () => {
  it("渲染平台标题", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { name: /BuildTest AI/i })).toBeInTheDocument();
  });
});
