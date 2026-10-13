# `ProgramFiles`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

Strata の Windows 用 Python コードで、NVIDIA の `nvml.dll` を追加探索する場所の組み立てと、MCP サーバーが「システムフォルダー内」とみなす範囲に使われます。どちらも Strata の Python サーバー／同梱ツールの処理です。エンジンの CUDA/HIP 実装がこの変数を直接読み取る箇所は確認できませんでした。

## 値と判定

`ProgramFiles` の文字列を数値や真偽値として parse しません。`os.environ.get("ProgramFiles", ...)` で値を得て、パスとして連結または正規化します。

| 状況 | Strata の扱い |
|---|---|
| Windows で未設定 | NVML 探索では `C:\Program Files` を既定の親フォルダーとして使う。MCP のシステムフォルダー一覧では `None` となり、一覧に加えない。 |
| Windows で空文字 | NVML 探索では既定値に置き換わらず、`NVIDIA Corporation\NVSMI\nvml.dll` という相対パス候補になる。MCP 側は空文字を false として除外する。 |
| Windows で非空文字列 | NVML 探索ではその文字列を親フォルダーにして候補を作る。MCP 側ではそのパスを正規化し、システムフォルダーとして扱う。 |
| Windows 以外 | MCP の `system_folders()` は Unix 系の固定パス一覧を返すため、この変数を参照しない。NVML の候補も `libnvidia-ml.so.1` と `libnvidia-ml.so` であり、この変数を使わない。 |

パスの妥当性をこの環境変数専用に検証する処理はありません。NVML の候補 DLL が読み込めない場合は `OSError` を捕捉して次の候補へ進みます。

## 有効になる条件

- telemetry の NVML 探索で使うのは `os.name == "nt"` の場合だけです。Strata はまず `nvml.dll` を名前で読み込み、失敗時に限り `ProgramFiles\NVIDIA Corporation\NVSMI\nvml.dll` を試します。したがって、この変数は最初の候補には影響しません。
- MCP サーバーの `check_data_dir()` は、新しいデータフォルダーを検査する分岐で `system_folders()` を呼びます。Strata の現在のデータフォルダー、Strata フォルダー内、またはその隣の既定 `Strata-data` は、このシステムフォルダー検査を通らず別条件で許可されます。
- MCP 側で新しいフォルダーがシステムフォルダーと一致するか、その配下にある場合、`data_dir ... is inside a system folder` として拒否します。Windows では `norm()` が絶対パス化・実パス化・大文字小文字を区別しない形への正規化を行います。

## 実行時の詳細

telemetry では、サーバーが `Telemetry` を作るときに各 GPU の reader を作成し、その中で `_Nvml` が `ProgramFiles` を読みます。このパス候補はその reader の初期化時に決まります。通常のサンプリングは同じ reader を使い続けます。一方、`free_vram_mib()` は呼び出しごとに新しい reader を作るため、その時点の `os.environ` の値を読み直します。サーバーの telemetry 初期化は `serve()` から `start_telemetry()` を通じて行われます。

MCP の `system_folders()` は `check_data_dir()` の検査時に呼ばれるため、その時点の環境を参照します。変数をプロセス内で変更した場合、以後の新しい reader 作成や MCP のパス検査には反映されますが、すでに作成済みの telemetry reader が保持する DLL 選択結果は変わりません。

既存ドキュメントは Monitor の GPU 情報や MCP の `data_dir` 制約を説明していますが、`ProgramFiles` の既定値や空文字の扱いは記載していません（`docs/DETAILS.md:451,659`; `docs/MCP_SERVER.md:175-181`）。

## 根拠

- `serve/telemetry.py:32-43`: Windows 時の NVML 候補と `ProgramFiles` の既定値、読み込み失敗時の次候補への移行。
- `serve/telemetry.py:249-262,330-365`: reader の生成、`free_vram_mib()` の都度生成、`Telemetry` 初期化時の reader 保持。
- `serve/server.py:3195-3203,5886-5889`: サーバー起動から telemetry 初期化への呼び出し経路。
- `tools/strata_mcp.py:371-382,1130-1154`: Windows での環境変数一覧作成と新規 `data_dir` に対するシステムフォルダー検査。
- `docs/MCP_SERVER.md:175-181`: MCP のデータフォルダー制約の説明。

同じ候補一覧にある `ProgramFiles(x86)` は別の環境変数です。`setup.py:1390-1415` の Visual Studio `vswhere.exe` 探索はそちらを読み取り、`ProgramFiles` 自体は読み取りません。
