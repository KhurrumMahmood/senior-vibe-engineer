interface PanelProps {
    open: boolean;
}

// Render the panel
export const handlePanelOpen = async (props: PanelProps): Promise<void> => {
    await Promise.resolve(props.open);
};
