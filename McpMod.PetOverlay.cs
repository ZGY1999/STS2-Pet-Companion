using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

#if !STS2_MCP_TESTS
using Godot;
#endif

namespace STS2_MCP;

public sealed record PetOverlayMenuItem(PetMode Mode, string Label, bool IsSelected);

public sealed record PetOverlayViewModel(
    PetMode Mode,
    PetVisualState VisualState,
    string ModeBadgeText,
    string BubbleTitle,
    string BubbleText,
    bool ShowBubble,
    bool ShowMenu,
    IReadOnlyList<PetOverlayMenuItem> MenuItems)
{
    public static PetOverlayViewModel FromSnapshot(PetStateSnapshot snapshot)
    {
        ArgumentNullException.ThrowIfNull(snapshot);

        var lines = snapshot.Lines
            .Where(line => !string.IsNullOrWhiteSpace(line))
            .ToArray();
        var bubbleText = string.Join('\n', lines);
        var bubbleTitle = snapshot.Title ?? string.Empty;
        var showBubble = bubbleTitle.Length > 0 || bubbleText.Length > 0;

        return new PetOverlayViewModel(
            snapshot.Mode,
            snapshot.State,
            ToModeBadgeText(snapshot.Mode),
            bubbleTitle,
            bubbleText,
            showBubble,
            snapshot.MenuOpen,
            BuildMenuItems(snapshot.Mode));
    }

    public bool HasEquivalentMenu(PetOverlayViewModel other)
    {
        ArgumentNullException.ThrowIfNull(other);

        if (MenuItems.Count != other.MenuItems.Count)
            return false;

        for (var index = 0; index < MenuItems.Count; index++)
        {
            var left = MenuItems[index];
            var right = other.MenuItems[index];
            if (left.Mode != right.Mode || left.Label != right.Label || left.IsSelected != right.IsSelected)
                return false;
        }

        return true;
    }

    private static IReadOnlyList<PetOverlayMenuItem> BuildMenuItems(PetMode selectedMode)
    {
        return new[]
        {
            new PetOverlayMenuItem(PetMode.Pause, "Pause", selectedMode == PetMode.Pause),
            new PetOverlayMenuItem(PetMode.Advise, "Advise", selectedMode == PetMode.Advise),
            new PetOverlayMenuItem(PetMode.Auto, "Auto", selectedMode == PetMode.Auto)
        };
    }

    private static string ToModeBadgeText(PetMode mode)
    {
        return mode switch
        {
            PetMode.Pause => "PAUSE",
            PetMode.Advise => "ADVISE",
            PetMode.Auto => "AUTO",
            _ => "PAUSE"
        };
    }
}

public enum PetOwlEyeState
{
    Wide,
    Focused,
    Closed,
    Crossed
}

public enum PetOwlWingPose
{
    Rest,
    Gesture,
    Talk,
    Dash
}

public sealed record PetOwlVisualSpec(
    PetOwlEyeState EyeState,
    PetOwlWingPose WingPose,
    bool BeakOpen,
    bool ShowChestRune,
    bool ShowTalkWaves,
    bool ShowSpeedLines,
    bool ShowErrorMarks,
    bool IsRuffled,
    float HeadTilt,
    float BodyLean)
{
    public static PetOwlVisualSpec FromState(PetVisualState state)
    {
        return state switch
        {
            PetVisualState.Thinking => new PetOwlVisualSpec(
                PetOwlEyeState.Focused,
                PetOwlWingPose.Gesture,
                false,
                true,
                false,
                false,
                false,
                false,
                -0.12f,
                0f),
            PetVisualState.Talking => new PetOwlVisualSpec(
                PetOwlEyeState.Wide,
                PetOwlWingPose.Talk,
                true,
                true,
                true,
                false,
                false,
                false,
                0f,
                0f),
            PetVisualState.AutoRunning => new PetOwlVisualSpec(
                PetOwlEyeState.Focused,
                PetOwlWingPose.Dash,
                false,
                true,
                false,
                true,
                false,
                false,
                0f,
                0.18f),
            PetVisualState.Paused => new PetOwlVisualSpec(
                PetOwlEyeState.Closed,
                PetOwlWingPose.Rest,
                false,
                true,
                false,
                false,
                false,
                false,
                0f,
                0f),
            PetVisualState.Error => new PetOwlVisualSpec(
                PetOwlEyeState.Crossed,
                PetOwlWingPose.Rest,
                false,
                true,
                false,
                false,
                true,
                true,
                0f,
                0f),
            _ => new PetOwlVisualSpec(
                PetOwlEyeState.Wide,
                PetOwlWingPose.Rest,
                false,
                true,
                false,
                false,
                false,
                false,
                0f,
                0f)
        };
    }
}

public sealed record PetOwlRenderRecipe(
    int TextureSize,
    float HeadRadiusX,
    float HeadRadiusY,
    float FaceRadiusX,
    float FaceRadiusY,
    float BodyRadiusX,
    float BodyRadiusY,
    float EyeRadius,
    float WingLift,
    float WingForward,
    float RuneScale,
    float OutlineThickness,
    float MotionLineLength,
    float FeatherJitter)
{
    public static PetOwlRenderRecipe FromState(PetVisualState state)
    {
        return state switch
        {
            PetVisualState.Thinking => new PetOwlRenderRecipe(136, 31f, 25f, 22f, 18f, 24f, 27f, 8.4f, -4f, 4f, 1f, 2.2f, 0f, 0f),
            PetVisualState.Talking => new PetOwlRenderRecipe(136, 31f, 25f, 22f, 18f, 24f, 27f, 8.9f, -7f, 7f, 1.08f, 2.2f, 0f, 0f),
            PetVisualState.AutoRunning => new PetOwlRenderRecipe(136, 30f, 24f, 21f, 17f, 23f, 26f, 8.2f, -2f, 13f, 1f, 2.3f, 18f, 0f),
            PetVisualState.Paused => new PetOwlRenderRecipe(136, 31f, 25f, 22f, 18f, 24f, 27f, 8.2f, 1f, 0f, 1f, 2.2f, 0f, 0f),
            PetVisualState.Error => new PetOwlRenderRecipe(136, 31f, 25f, 22f, 18f, 24f, 27f, 8.6f, 1f, 0f, 1f, 2.4f, 0f, 3f),
            _ => new PetOwlRenderRecipe(136, 31f, 25f, 22f, 18f, 24f, 27f, 8.6f, 0f, 0f, 1f, 2.2f, 0f, 0f)
        };
    }
}

public sealed record PetOwlAssetManifest(string RelativeDirectory)
{
    public static PetOwlAssetManifest Default { get; } = new("pet/owl");

    public string GetRelativePath(PetVisualState state)
    {
        var parts = RelativeDirectory
            .Split(new[] { '/', '\\' }, StringSplitOptions.RemoveEmptyEntries)
            .Append(GetFileName(state))
            .ToArray();
        return Path.Combine(parts);
    }

    public string[] BuildCandidatePaths(string baseDirectory, PetVisualState state)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(baseDirectory);

        var relativePath = GetRelativePath(state);
        return new[]
        {
            Path.Combine(baseDirectory, "STS2_MCP.assets", relativePath),
            Path.Combine(baseDirectory, relativePath)
        };
    }

    private static string GetFileName(PetVisualState state)
    {
        return state switch
        {
            PetVisualState.Thinking => "thinking.png",
            PetVisualState.Talking => "talking.png",
            PetVisualState.AutoRunning => "auto_running.png",
            PetVisualState.Paused => "paused.png",
            PetVisualState.Error => "error.png",
            _ => "idle.png"
        };
    }
}

public static class PetOwlAssetSanitizer
{
    public const int DefaultChromaThreshold = 18;
    public const int DefaultExpansionSteps = 3;

    public static bool IsLikelySpriteAnchor(byte red, byte green, byte blue, byte alpha)
    {
        if (alpha == 0)
            return false;

        var max = Math.Max(red, Math.Max(green, blue));
        var min = Math.Min(red, Math.Min(green, blue));
        return max - min >= DefaultChromaThreshold;
    }

    public static bool[,] ExpandMask(bool[,] seedMask, int expansionSteps)
    {
        ArgumentNullException.ThrowIfNull(seedMask);

        if (expansionSteps <= 0)
            return (bool[,])seedMask.Clone();

        var width = seedMask.GetLength(0);
        var height = seedMask.GetLength(1);
        var current = (bool[,])seedMask.Clone();

        for (var step = 0; step < expansionSteps; step++)
        {
            var next = (bool[,])current.Clone();

            for (var x = 0; x < width; x++)
            {
                for (var y = 0; y < height; y++)
                {
                    if (!current[x, y])
                        continue;

                    for (var offsetX = -1; offsetX <= 1; offsetX++)
                    {
                        for (var offsetY = -1; offsetY <= 1; offsetY++)
                        {
                            var nx = x + offsetX;
                            var ny = y + offsetY;
                            if (nx >= 0 && ny >= 0 && nx < width && ny < height)
                                next[nx, ny] = true;
                        }
                    }
                }
            }

            current = next;
        }

        return current;
    }
}

#if !STS2_MCP_TESTS
internal sealed class PetOverlayController
{
    private const float OverlayWidth = 210f;
    private const float OverlayHeight = 164f;
    private const float OverlayRightMargin = 18f;
    private const float OverlayTopMargin = 86f;

    private readonly PetStateStore _store;
    private CanvasLayer? _layer;
    private Control? _root;
    private Control? _menuDismissOverlay;
    private VBoxContainer? _stack;
    private PanelContainer? _bubblePanel;
    private Label? _bubbleTitle;
    private Label? _bubbleBody;
    private PanelContainer? _menuPanel;
    private VBoxContainer? _menuList;
    private Label? _badgeLabel;
    private TextureRect? _petSprite;
    private PetOverlayViewModel? _lastViewModel;

    public PetOverlayController(PetStateStore store)
    {
        _store = store ?? throw new ArgumentNullException(nameof(store));
    }

    public void EnsureAttached(SceneTree tree)
    {
        if (GodotObject.IsInstanceValid(_layer))
            return;

        if (!GodotObject.IsInstanceValid(tree.Root))
            return;

        BuildTree();
        tree.Root.AddChild(_layer);
        Refresh();
    }

    public void Refresh()
    {
        if (!GodotObject.IsInstanceValid(_root))
            return;

        var viewModel = PetOverlayViewModel.FromSnapshot(_store.Snapshot());

        if (_bubblePanel != null)
            _bubblePanel.Visible = viewModel.ShowBubble;

        if (_bubbleTitle != null)
            _bubbleTitle.Text = viewModel.BubbleTitle;

        if (_bubbleBody != null)
            _bubbleBody.Text = viewModel.BubbleText;

        if (_menuPanel != null)
            _menuPanel.Visible = viewModel.ShowMenu;

        if (_menuDismissOverlay != null)
            _menuDismissOverlay.Visible = viewModel.ShowMenu;

        if (_badgeLabel != null)
            _badgeLabel.Text = viewModel.ModeBadgeText;

        if (_petSprite != null)
            _petSprite.Texture = PetOwlTextureFactory.GetTexture(viewModel.VisualState);

        if (_lastViewModel == null || !_lastViewModel.HasEquivalentMenu(viewModel))
            RebuildMenu(viewModel);

        _lastViewModel = viewModel;
    }

    private void BuildTree()
    {
        _layer = new CanvasLayer
        {
            Name = "STS2MCPPetOverlay",
            Layer = 60
        };

        _root = new Control
        {
            Name = "Root",
            MouseFilter = Control.MouseFilterEnum.Ignore
        };
        _root.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
        _layer.AddChild(_root);

        _menuDismissOverlay = new Control
        {
            Name = "MenuDismissOverlay",
            Visible = false,
            MouseFilter = Control.MouseFilterEnum.Stop
        };
        _menuDismissOverlay.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
        _menuDismissOverlay.GuiInput += OnDismissOverlayGuiInput;
        _root.AddChild(_menuDismissOverlay);

        _stack = new VBoxContainer
        {
            Name = "CornerStack",
            MouseFilter = Control.MouseFilterEnum.Ignore,
            Alignment = BoxContainer.AlignmentMode.End
        };
        _stack.AnchorLeft = 1;
        _stack.AnchorTop = 0;
        _stack.AnchorRight = 1;
        _stack.AnchorBottom = 0;
        _stack.OffsetLeft = -(OverlayRightMargin + OverlayWidth);
        _stack.OffsetTop = OverlayTopMargin;
        _stack.OffsetRight = -OverlayRightMargin;
        _stack.OffsetBottom = OverlayTopMargin + OverlayHeight;
        _root.AddChild(_stack);

        _bubblePanel = new PanelContainer
        {
            Name = "Bubble",
            Visible = false,
            MouseFilter = Control.MouseFilterEnum.Ignore,
            CustomMinimumSize = new Vector2(186, 0)
        };
        _bubblePanel.AddThemeStyleboxOverride("panel", CreatePanelStyle(new Color(0.09f, 0.10f, 0.15f, 0.92f), 18));
        _stack.AddChild(_bubblePanel);

        var bubbleContent = new VBoxContainer();
        bubbleContent.AddThemeConstantOverride("separation", 4);
        _bubblePanel.AddChild(bubbleContent);

        _bubbleTitle = new Label
        {
            HorizontalAlignment = HorizontalAlignment.Left
        };
        _bubbleTitle.AddThemeColorOverride("font_color", new Color(1f, 0.95f, 0.80f));
        bubbleContent.AddChild(_bubbleTitle);

        _bubbleBody = new Label
        {
            HorizontalAlignment = HorizontalAlignment.Left,
            AutowrapMode = TextServer.AutowrapMode.WordSmart
        };
        _bubbleBody.AddThemeColorOverride("font_color", Colors.White);
        bubbleContent.AddChild(_bubbleBody);

        _menuPanel = new PanelContainer
        {
            Name = "ModeMenu",
            Visible = false,
            MouseFilter = Control.MouseFilterEnum.Stop,
            CustomMinimumSize = new Vector2(136, 0)
        };
        _menuPanel.AddThemeStyleboxOverride("panel", CreatePanelStyle(new Color(0.08f, 0.09f, 0.12f, 0.95f), 16));
        _stack.AddChild(_menuPanel);

        _menuList = new VBoxContainer();
        _menuList.AddThemeConstantOverride("separation", 6);
        _menuPanel.AddChild(_menuList);

        var footer = new HBoxContainer
        {
            Alignment = BoxContainer.AlignmentMode.End,
            MouseFilter = Control.MouseFilterEnum.Ignore
        };
        footer.AddThemeConstantOverride("separation", 8);
        _stack.AddChild(footer);

        var badgePanel = new PanelContainer
        {
            MouseFilter = Control.MouseFilterEnum.Ignore
        };
        badgePanel.AddThemeStyleboxOverride("panel", CreatePanelStyle(new Color(0.12f, 0.17f, 0.20f, 0.94f), 14));
        footer.AddChild(badgePanel);

        _badgeLabel = new Label();
        _badgeLabel.AddThemeColorOverride("font_color", new Color(0.82f, 0.95f, 1.0f));
        badgePanel.AddChild(_badgeLabel);

        var petPanel = new PanelContainer
        {
            MouseFilter = Control.MouseFilterEnum.Stop,
            CustomMinimumSize = new Vector2(68, 68),
            MouseDefaultCursorShape = Control.CursorShape.PointingHand
        };
        petPanel.AddThemeStyleboxOverride(
            "panel",
            CreatePanelStyle(
                new Color(0.16f, 0.13f, 0.10f, 0.96f),
                28,
                0,
                0,
                0,
                0));
        petPanel.GuiInput += OnPetGuiInput;
        footer.AddChild(petPanel);

        _petSprite = new TextureRect
        {
            CustomMinimumSize = new Vector2(68, 68),
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
            MouseFilter = Control.MouseFilterEnum.Ignore,
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
            StretchMode = TextureRect.StretchModeEnum.Scale
        };
        _petSprite.Texture = PetOwlTextureFactory.GetTexture(PetVisualState.Paused);
        petPanel.AddChild(_petSprite);
    }

    private void RebuildMenu(PetOverlayViewModel viewModel)
    {
        if (_menuList == null)
            return;

        foreach (var child in _menuList.GetChildren())
        {
            child.QueueFree();
        }

        foreach (var item in viewModel.MenuItems)
        {
            var selectedMode = item.Mode;
            var button = new Button
            {
                Text = item.Label,
                Flat = false,
                Alignment = HorizontalAlignment.Left,
                MouseFilter = Control.MouseFilterEnum.Stop,
                MouseDefaultCursorShape = Control.CursorShape.PointingHand,
                FocusMode = Control.FocusModeEnum.None,
                ActionMode = BaseButton.ActionModeEnum.Press
            };
            button.SizeFlagsHorizontal = Control.SizeFlags.ExpandFill;
            button.AddThemeStyleboxOverride(
                "normal",
                CreateButtonStyle(item.IsSelected
                    ? new Color(0.27f, 0.38f, 0.31f, 0.98f)
                    : new Color(0.16f, 0.17f, 0.20f, 0.96f)));
            button.AddThemeStyleboxOverride(
                "hover",
                CreateButtonStyle(item.IsSelected
                    ? new Color(0.31f, 0.42f, 0.36f, 0.98f)
                    : new Color(0.22f, 0.24f, 0.28f, 0.98f)));
            button.AddThemeStyleboxOverride(
                "pressed",
                CreateButtonStyle(item.IsSelected
                    ? new Color(0.22f, 0.34f, 0.28f, 0.98f)
                    : new Color(0.14f, 0.22f, 0.31f, 0.98f)));
            button.AddThemeColorOverride("font_color", Colors.White);
            button.AddThemeColorOverride("font_hover_color", Colors.White);
            button.AddThemeColorOverride("font_pressed_color", Colors.White);
            button.ButtonDown += () => SelectMode(selectedMode);
            _menuList.AddChild(button);
        }
    }

    private void OnPetGuiInput(InputEvent @event)
    {
        if (@event is not InputEventMouseButton { Pressed: true } mouseButton)
            return;

        if (mouseButton.ButtonIndex is not (MouseButton.Left or MouseButton.Right))
            return;

        _store.ToggleMenu();
        Refresh();
    }

    private void OnDismissOverlayGuiInput(InputEvent @event)
    {
        if (@event is not InputEventMouseButton { Pressed: true } mouseButton)
            return;

        if (mouseButton.ButtonIndex is not (MouseButton.Left or MouseButton.Right))
            return;

        _store.SetMenuOpen(false);
        Refresh();
        _menuDismissOverlay?.AcceptEvent();
    }

    private void SelectMode(PetMode mode)
    {
        _store.SetMode(mode);
        _store.SetMenuOpen(false);
        Refresh();
    }

    private static StyleBoxFlat CreatePanelStyle(
        Color color,
        int cornerRadius,
        int contentMarginLeft = 14,
        int contentMarginTop = 10,
        int contentMarginRight = 14,
        int contentMarginBottom = 10)
    {
        return new StyleBoxFlat
        {
            BgColor = color,
            CornerRadiusTopLeft = cornerRadius,
            CornerRadiusTopRight = cornerRadius,
            CornerRadiusBottomRight = cornerRadius,
            CornerRadiusBottomLeft = cornerRadius,
            ContentMarginLeft = contentMarginLeft,
            ContentMarginRight = contentMarginRight,
            ContentMarginTop = contentMarginTop,
            ContentMarginBottom = contentMarginBottom,
            BorderWidthLeft = 1,
            BorderWidthTop = 1,
            BorderWidthRight = 1,
            BorderWidthBottom = 1,
            BorderColor = new Color(1f, 1f, 1f, 0.08f)
        };
    }

    private static StyleBoxFlat CreateButtonStyle(Color color)
    {
        return new StyleBoxFlat
        {
            BgColor = color,
            CornerRadiusTopLeft = 12,
            CornerRadiusTopRight = 12,
            CornerRadiusBottomRight = 12,
            CornerRadiusBottomLeft = 12,
            ContentMarginLeft = 10,
            ContentMarginRight = 10,
            ContentMarginTop = 8,
            ContentMarginBottom = 8
        };
    }
}

internal static class PetOwlTextureFactory
{
    private static readonly Dictionary<PetVisualState, Texture2D> _cache = new();
    private static readonly HashSet<PetVisualState> _loggedFallbackStates = new();
    private static readonly HashSet<PetVisualState> _loggedExternalStates = new();

    public static Texture2D GetTexture(PetVisualState state)
    {
        if (_cache.TryGetValue(state, out var texture))
            return texture;

        texture = TryLoadExternalTexture(state) ?? BuildTexture(state);
        _cache[state] = texture;
        return texture;
    }

    private static Texture2D? TryLoadExternalTexture(PetVisualState state)
    {
        var assemblyDirectory = Path.GetDirectoryName(typeof(McpMod).Assembly.Location);
        if (string.IsNullOrWhiteSpace(assemblyDirectory))
            return null;

        foreach (var candidate in PetOwlAssetManifest.Default.BuildCandidatePaths(assemblyDirectory, state))
        {
            if (!File.Exists(candidate))
                continue;

            var image = Image.LoadFromFile(candidate);
            if (image.GetWidth() <= 0 || image.GetHeight() <= 0)
                continue;

            SanitizeExternalImage(image);

            if (_loggedExternalStates.Add(state))
                GD.Print($"[STS2 MCP] Loaded pet asset for {state} from {candidate}");

            return ImageTexture.CreateFromImage(image);
        }

        if (_loggedFallbackStates.Add(state))
            GD.Print($"[STS2 MCP] No external pet asset found for {state}; using generated fallback.");

        return null;
    }

    private static Texture2D BuildTexture(PetVisualState state)
    {
        var spec = PetOwlVisualSpec.FromState(state);
        var recipe = PetOwlRenderRecipe.FromState(state);
        var image = Image.CreateEmpty(recipe.TextureSize, recipe.TextureSize, false, Image.Format.Rgba8);
        image.Fill(Colors.Transparent);

        var scale = recipe.TextureSize / 68f;
        var bodyCenter = new Vector2(recipe.TextureSize * 0.5f + spec.BodyLean * 8f * scale, 43f * scale);
        var headCenter = new Vector2(recipe.TextureSize * 0.5f + spec.BodyLean * 5f * scale, 21f * scale + spec.HeadTilt * 6f * scale);

        var outline = new Color(0.10f, 0.09f, 0.18f, 1f);
        var bodyBase = spec.IsRuffled ? new Color(0.28f, 0.29f, 0.57f, 1f) : new Color(0.24f, 0.25f, 0.54f, 1f);
        var bodyShade = new Color(0.15f, 0.15f, 0.33f, 1f);
        var faceMask = new Color(0.72f, 0.81f, 1.0f, 1f);
        var faceShade = new Color(0.50f, 0.61f, 0.91f, 1f);
        var glowBlue = new Color(0.38f, 0.90f, 1f, 1f);
        var gold = new Color(0.98f, 0.78f, 0.34f, 1f);
        var footColor = new Color(0.74f, 0.54f, 0.24f, 1f);
        var errorRed = new Color(0.90f, 0.24f, 0.28f, 1f);

        FillEllipse(image, bodyCenter + new Vector2(0f, 8f * scale), new Vector2(recipe.BodyRadiusX * 0.92f * scale, recipe.BodyRadiusY * 0.96f * scale), new Color(0f, 0f, 0f, 0.15f));

        if (spec.ShowSpeedLines && recipe.MotionLineLength > 0f)
            DrawSpeedLines(image, bodyCenter, glowBlue, recipe.MotionLineLength * scale);

        DrawTail(image, bodyCenter, bodyShade, outline, scale, recipe.OutlineThickness);
        DrawBody(image, bodyCenter, recipe, bodyBase, bodyShade, outline, spec.IsRuffled, scale);
        DrawWing(image, bodyCenter, recipe, true, spec.WingPose, bodyBase, outline, scale);
        DrawWing(image, bodyCenter, recipe, false, spec.WingPose, bodyBase, outline, scale);
        DrawHead(image, headCenter, recipe, bodyBase, outline, scale);
        DrawFaceMask(image, headCenter, recipe, faceMask, faceShade, scale);
        DrawFeet(image, bodyCenter, footColor, outline, scale);

        if (spec.ShowChestRune)
            DrawChestRune(image, bodyCenter, gold, scale, recipe.RuneScale);

        DrawBeak(image, headCenter, gold, outline, spec.BeakOpen, scale);
        DrawEyes(image, headCenter, recipe, spec, glowBlue, outline, errorRed, scale);

        if (spec.ShowTalkWaves)
            DrawTalkWaves(image, headCenter, glowBlue, scale);

        if (spec.ShowErrorMarks)
            DrawErrorMarks(image, headCenter, errorRed, scale);

        if (recipe.FeatherJitter > 0f)
            DrawFeatherJitter(image, bodyCenter, outline, recipe.FeatherJitter * scale);

        image.Resize(68, 68, Image.Interpolation.Bilinear);
        return ImageTexture.CreateFromImage(image);
    }

    private static void SanitizeExternalImage(Image image)
    {
        var width = image.GetWidth();
        var height = image.GetHeight();
        if (width <= 0 || height <= 0)
            return;

        var seedMask = new bool[width, height];
        var hasColoredAnchors = false;

        for (var x = 0; x < width; x++)
        {
            for (var y = 0; y < height; y++)
            {
                var color = image.GetPixel(x, y);
                var alpha = (byte)Math.Clamp((int)MathF.Round(color.A * 255f), 0, 255);
                var red = (byte)Math.Clamp((int)MathF.Round(color.R * 255f), 0, 255);
                var green = (byte)Math.Clamp((int)MathF.Round(color.G * 255f), 0, 255);
                var blue = (byte)Math.Clamp((int)MathF.Round(color.B * 255f), 0, 255);

                if (!PetOwlAssetSanitizer.IsLikelySpriteAnchor(red, green, blue, alpha))
                    continue;

                seedMask[x, y] = true;
                hasColoredAnchors = true;
            }
        }

        if (!hasColoredAnchors)
            return;

        var protectedMask = PetOwlAssetSanitizer.ExpandMask(seedMask, PetOwlAssetSanitizer.DefaultExpansionSteps);
        var transparent = Colors.Transparent;

        for (var x = 0; x < width; x++)
        {
            for (var y = 0; y < height; y++)
            {
                if (!protectedMask[x, y])
                    image.SetPixel(x, y, transparent);
            }
        }
    }

    private static void DrawTail(Image image, Vector2 bodyCenter, Color color, Color outline, float scale, float outlineThickness)
    {
        FillTriangle(image, bodyCenter + new Vector2(-8f, 20f) * scale, bodyCenter + new Vector2(0f, 30f) * scale, bodyCenter + new Vector2(8f, 20f) * scale, color);
        DrawLine(image, bodyCenter + new Vector2(-8f, 20f) * scale, bodyCenter + new Vector2(0f, 30f) * scale, outline, (int)MathF.Round(outlineThickness));
        DrawLine(image, bodyCenter + new Vector2(0f, 30f) * scale, bodyCenter + new Vector2(8f, 20f) * scale, outline, (int)MathF.Round(outlineThickness));
    }

    private static void DrawBody(Image image, Vector2 bodyCenter, PetOwlRenderRecipe recipe, Color fill, Color shade, Color outline, bool isRuffled, float scale)
    {
        FillEllipse(image, bodyCenter, new Vector2(recipe.BodyRadiusX * scale, recipe.BodyRadiusY * scale), fill);
        FillEllipse(image, bodyCenter + new Vector2(0f, 7f * scale), new Vector2(recipe.BodyRadiusX * 0.62f * scale, recipe.BodyRadiusY * 0.58f * scale), shade);
        OutlineEllipse(image, bodyCenter, new Vector2(recipe.BodyRadiusX * scale, recipe.BodyRadiusY * scale), outline, recipe.OutlineThickness);

        if (isRuffled)
        {
            DrawLine(image, bodyCenter + new Vector2(-15f, -2f) * scale, bodyCenter + new Vector2(-20f, 2f) * scale, outline, 1);
            DrawLine(image, bodyCenter + new Vector2(15f, -2f) * scale, bodyCenter + new Vector2(20f, 2f) * scale, outline, 1);
        }
    }

    private static void DrawWing(Image image, Vector2 bodyCenter, PetOwlRenderRecipe recipe, bool isLeft, PetOwlWingPose pose, Color fill, Color outline, float scale)
    {
        var side = isLeft ? -1f : 1f;
        var shoulder = pose switch
        {
            PetOwlWingPose.Gesture when !isLeft => bodyCenter + new Vector2((6f + recipe.WingForward) * scale, (-2f + recipe.WingLift) * scale),
            PetOwlWingPose.Talk when !isLeft => bodyCenter + new Vector2((8f + recipe.WingForward) * scale, recipe.WingLift * scale),
            PetOwlWingPose.Dash => bodyCenter + new Vector2(side * 3f * scale, 7f * scale),
            _ => bodyCenter + new Vector2(side * 13f * scale, (5f + recipe.WingLift * 0.2f) * scale)
        };
        var tip = pose switch
        {
            PetOwlWingPose.Gesture when !isLeft => bodyCenter + new Vector2(24f * scale, 10f * scale),
            PetOwlWingPose.Talk when !isLeft => bodyCenter + new Vector2(22f * scale, 15f * scale),
            PetOwlWingPose.Dash => bodyCenter + new Vector2(side * (18f + recipe.WingForward) * scale, (-4f + recipe.WingLift) * scale),
            _ => bodyCenter + new Vector2(side * 20f * scale, 18f * scale)
        };
        var tail = bodyCenter + new Vector2(side * 10f * scale, 18f * scale);
        FillTriangle(image, shoulder, tip, tail, fill);
        DrawLine(image, shoulder, tip, outline, 1);
        DrawLine(image, tip, tail, outline, 1);
    }

    private static void DrawHead(Image image, Vector2 headCenter, PetOwlRenderRecipe recipe, Color fill, Color outline, float scale)
    {
        FillEllipse(image, headCenter + new Vector2(0f, 2f * scale), new Vector2(recipe.HeadRadiusX * scale, recipe.HeadRadiusY * scale), fill);
        OutlineEllipse(image, headCenter + new Vector2(0f, 2f * scale), new Vector2(recipe.HeadRadiusX * scale, recipe.HeadRadiusY * scale), outline, recipe.OutlineThickness);
        FillTriangle(image, headCenter + new Vector2(-14f, -3f) * scale, headCenter + new Vector2(-19f, -14f) * scale, headCenter + new Vector2(-6f, -10f) * scale, fill);
        FillTriangle(image, headCenter + new Vector2(14f, -3f) * scale, headCenter + new Vector2(19f, -14f) * scale, headCenter + new Vector2(6f, -10f) * scale, fill);
    }

    private static void DrawFaceMask(Image image, Vector2 headCenter, PetOwlRenderRecipe recipe, Color fill, Color shade, float scale)
    {
        FillEllipse(image, headCenter + new Vector2(0f, 4f * scale), new Vector2(recipe.FaceRadiusX * scale, recipe.FaceRadiusY * scale), fill);
        FillTriangle(image, headCenter + new Vector2(-11f, 14f) * scale, headCenter + new Vector2(0f, 23f) * scale, headCenter + new Vector2(11f, 14f) * scale, shade);
    }

    private static void DrawFeet(Image image, Vector2 bodyCenter, Color fill, Color outline, float scale)
    {
        DrawFoot(image, bodyCenter + new Vector2(-7f, 26f) * scale, fill, outline, scale);
        DrawFoot(image, bodyCenter + new Vector2(7f, 26f) * scale, fill, outline, scale);
    }

    private static void DrawFoot(Image image, Vector2 center, Color fill, Color outline, float scale)
    {
        DrawLine(image, center + new Vector2(-3f, 0f) * scale, center + new Vector2(-5f, 4f) * scale, fill, 1);
        DrawLine(image, center + new Vector2(0f, 0f) * scale, center + new Vector2(0f, 4f) * scale, fill, 1);
        DrawLine(image, center + new Vector2(3f, 0f) * scale, center + new Vector2(5f, 4f) * scale, fill, 1);
    }

    private static void DrawChestRune(Image image, Vector2 bodyCenter, Color color, float scale, float runeScale)
    {
        var vertical = 7f * runeScale * scale;
        var arm = 5.5f * runeScale * scale;
        DrawLine(image, bodyCenter + new Vector2(-1f * scale, -vertical), bodyCenter + new Vector2(-1f * scale, vertical), color, 2);
        DrawLine(image, bodyCenter + new Vector2(-1f * scale, -vertical), bodyCenter + new Vector2(arm, -1f * scale), color, 2);
        DrawLine(image, bodyCenter + new Vector2(arm, -1f * scale), bodyCenter + new Vector2(-1f * scale, vertical), color, 2);
    }

    private static void DrawBeak(Image image, Vector2 headCenter, Color fill, Color outline, bool beakOpen, float scale)
    {
        FillTriangle(image, headCenter + new Vector2(-5f, 10f) * scale, headCenter + new Vector2(5f, 10f) * scale, headCenter + new Vector2(0f, 17f) * scale, fill);

        if (!beakOpen)
            return;

        FillTriangle(image, headCenter + new Vector2(-4f, 17f) * scale, headCenter + new Vector2(4f, 17f) * scale, headCenter + new Vector2(0f, 21f) * scale, new Color(0.88f, 0.56f, 0.20f, 1f));
    }

    private static void DrawEyes(Image image, Vector2 headCenter, PetOwlRenderRecipe recipe, PetOwlVisualSpec spec, Color glowBlue, Color outline, Color errorRed, float scale)
    {
        var leftEye = headCenter + new Vector2(-8f * scale, 2f * scale);
        var rightEye = headCenter + new Vector2(8f * scale, 2f * scale);

        switch (spec.EyeState)
        {
            case PetOwlEyeState.Closed:
                DrawArc(image, leftEye, 5f * scale, 0.4f, 2.7f, outline);
                DrawArc(image, rightEye, 5f * scale, 0.4f, 2.7f, outline);
                return;
            case PetOwlEyeState.Crossed:
                DrawEyeCross(image, leftEye, errorRed, scale);
                DrawEyeCross(image, rightEye, errorRed, scale);
                return;
        }

        var eyeRadius = recipe.EyeRadius * scale;
        var pupilOffsetY = spec.EyeState == PetOwlEyeState.Focused ? 1.5f * scale : 0.3f * scale;
        FillCircle(image, leftEye, eyeRadius, glowBlue);
        FillCircle(image, rightEye, eyeRadius, glowBlue);
        FillCircle(image, leftEye + new Vector2(0f, pupilOffsetY), 3.2f * scale, outline);
        FillCircle(image, rightEye + new Vector2(0f, pupilOffsetY), 3.2f * scale, outline);
        FillCircle(image, leftEye + new Vector2(-2.1f * scale, -2.4f * scale), 1.3f * scale, Colors.White);
        FillCircle(image, rightEye + new Vector2(-2.1f * scale, -2.4f * scale), 1.3f * scale, Colors.White);
    }

    private static void DrawTalkWaves(Image image, Vector2 headCenter, Color color, float scale)
    {
        DrawArc(image, headCenter + new Vector2(19f, 4f) * scale, 5f * scale, -0.8f, 0.8f, color);
        DrawArc(image, headCenter + new Vector2(26f, 4f) * scale, 7f * scale, -0.8f, 0.8f, color);
    }

    private static void DrawErrorMarks(Image image, Vector2 headCenter, Color color, float scale)
    {
        DrawLine(image, headCenter + new Vector2(-17f, -12f) * scale, headCenter + new Vector2(-10f, -18f) * scale, color, 2);
        DrawLine(image, headCenter + new Vector2(-17f, -18f) * scale, headCenter + new Vector2(-10f, -12f) * scale, color, 2);
        DrawLine(image, headCenter + new Vector2(10f, -12f) * scale, headCenter + new Vector2(17f, -18f) * scale, color, 2);
        DrawLine(image, headCenter + new Vector2(10f, -18f) * scale, headCenter + new Vector2(17f, -12f) * scale, color, 2);
    }

    private static void DrawSpeedLines(Image image, Vector2 bodyCenter, Color color, float length)
    {
        DrawLine(image, bodyCenter + new Vector2(-length, -8f), bodyCenter + new Vector2(-10f, -8f), color, 2);
        DrawLine(image, bodyCenter + new Vector2(-(length - 4f), 2f), bodyCenter + new Vector2(-8f, 2f), color, 2);
        DrawLine(image, bodyCenter + new Vector2(-(length - 8f), 12f), bodyCenter + new Vector2(-6f, 12f), color, 2);
    }

    private static void DrawEyeCross(Image image, Vector2 center, Color color, float scale)
    {
        DrawLine(image, center + new Vector2(-4f, -4f) * scale, center + new Vector2(4f, 4f) * scale, color, 2);
        DrawLine(image, center + new Vector2(-4f, 4f) * scale, center + new Vector2(4f, -4f) * scale, color, 2);
    }

    private static void DrawFeatherJitter(Image image, Vector2 bodyCenter, Color color, float amount)
    {
        DrawLine(image, bodyCenter + new Vector2(-20f, -6f), bodyCenter + new Vector2(-24f, -6f - amount), color, 1);
        DrawLine(image, bodyCenter + new Vector2(20f, -6f), bodyCenter + new Vector2(24f, -6f - amount), color, 1);
        DrawLine(image, bodyCenter + new Vector2(0f, -24f), bodyCenter + new Vector2(0f, -28f - amount), color, 1);
    }

    private static void FillEllipse(Image image, Vector2 center, Vector2 radius, Color color)
    {
        var minX = Math.Max(0, (int)MathF.Floor(center.X - radius.X));
        var maxX = Math.Min(image.GetWidth() - 1, (int)MathF.Ceiling(center.X + radius.X));
        var minY = Math.Max(0, (int)MathF.Floor(center.Y - radius.Y));
        var maxY = Math.Min(image.GetHeight() - 1, (int)MathF.Ceiling(center.Y + radius.Y));

        for (var y = minY; y <= maxY; y++)
        {
            for (var x = minX; x <= maxX; x++)
            {
                var dx = (x - center.X) / radius.X;
                var dy = (y - center.Y) / radius.Y;
                if (dx * dx + dy * dy <= 1f)
                    image.SetPixel(x, y, color);
            }
        }
    }

    private static void OutlineEllipse(Image image, Vector2 center, Vector2 radius, Color color, float thickness)
    {
        var minX = Math.Max(0, (int)MathF.Floor(center.X - radius.X - thickness));
        var maxX = Math.Min(image.GetWidth() - 1, (int)MathF.Ceiling(center.X + radius.X + thickness));
        var minY = Math.Max(0, (int)MathF.Floor(center.Y - radius.Y - thickness));
        var maxY = Math.Min(image.GetHeight() - 1, (int)MathF.Ceiling(center.Y + radius.Y + thickness));

        for (var y = minY; y <= maxY; y++)
        {
            for (var x = minX; x <= maxX; x++)
            {
                var dx = (x - center.X) / radius.X;
                var dy = (y - center.Y) / radius.Y;
                var dist = dx * dx + dy * dy;
                if (dist <= 1f && dist >= 1f - (0.12f * thickness))
                    image.SetPixel(x, y, color);
            }
        }
    }

    private static void FillCircle(Image image, Vector2 center, float radius, Color color)
    {
        FillEllipse(image, center, new Vector2(radius, radius), color);
    }

    private static void FillTriangle(Image image, Vector2 a, Vector2 b, Vector2 c, Color color)
    {
        var minX = Math.Max(0, (int)MathF.Floor(MathF.Min(a.X, MathF.Min(b.X, c.X))));
        var maxX = Math.Min(image.GetWidth() - 1, (int)MathF.Ceiling(MathF.Max(a.X, MathF.Max(b.X, c.X))));
        var minY = Math.Max(0, (int)MathF.Floor(MathF.Min(a.Y, MathF.Min(b.Y, c.Y))));
        var maxY = Math.Min(image.GetHeight() - 1, (int)MathF.Ceiling(MathF.Max(a.Y, MathF.Max(b.Y, c.Y))));

        var area = Edge(a, b, c);
        if (MathF.Abs(area) < 0.01f)
            return;

        for (var y = minY; y <= maxY; y++)
        {
            for (var x = minX; x <= maxX; x++)
            {
                var p = new Vector2(x + 0.5f, y + 0.5f);
                var w0 = Edge(b, c, p);
                var w1 = Edge(c, a, p);
                var w2 = Edge(a, b, p);
                if ((w0 >= 0f && w1 >= 0f && w2 >= 0f) || (w0 <= 0f && w1 <= 0f && w2 <= 0f))
                    image.SetPixel(x, y, color);
            }
        }
    }

    private static float Edge(Vector2 a, Vector2 b, Vector2 c)
    {
        return (c.X - a.X) * (b.Y - a.Y) - (c.Y - a.Y) * (b.X - a.X);
    }

    private static void DrawLine(Image image, Vector2 from, Vector2 to, Color color, int thickness)
    {
        var steps = (int)MathF.Max(MathF.Abs(to.X - from.X), MathF.Abs(to.Y - from.Y));
        if (steps == 0)
        {
            StampPixel(image, (int)MathF.Round(from.X), (int)MathF.Round(from.Y), color, thickness);
            return;
        }

        for (var step = 0; step <= steps; step++)
        {
            var t = step / (float)steps;
            var x = Mathf.Lerp(from.X, to.X, t);
            var y = Mathf.Lerp(from.Y, to.Y, t);
            StampPixel(image, (int)MathF.Round(x), (int)MathF.Round(y), color, thickness);
        }
    }

    private static void DrawArc(Image image, Vector2 center, float radius, float startAngle, float endAngle, Color color)
    {
        const int steps = 20;
        Vector2? last = null;
        for (var index = 0; index <= steps; index++)
        {
            var t = index / (float)steps;
            var angle = Mathf.Lerp(startAngle, endAngle, t);
            var point = center + new Vector2(MathF.Cos(angle) * radius, MathF.Sin(angle) * radius);
            if (last.HasValue)
                DrawLine(image, last.Value, point, color, 1);
            last = point;
        }
    }

    private static void StampPixel(Image image, int x, int y, Color color, int thickness)
    {
        for (var offsetY = -thickness; offsetY <= thickness; offsetY++)
        {
            for (var offsetX = -thickness; offsetX <= thickness; offsetX++)
            {
                var px = x + offsetX;
                var py = y + offsetY;
                if (px >= 0 && py >= 0 && px < image.GetWidth() && py < image.GetHeight())
                    image.SetPixel(px, py, color);
            }
        }
    }
}
#endif
