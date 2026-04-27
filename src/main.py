"""Streamlit entrypoint for the thuisbatterij simulator."""

from __future__ import annotations

import streamlit as st


def main() -> None:
    st.set_page_config(page_title="Thuisbatterij Simulator", layout="wide")
    st.title("Thuisbatterij Simulator")
    st.info("Implementatie gestart. DataManager is de eerste module in aanbouw.")


if __name__ == "__main__":
    main()

