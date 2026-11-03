# `FNX_LAB_DIR`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

同梱の sFNX 検証ツール `fnx_run` の `exact` モードが、生成した logits と基準データを置く lab ディレクトリを指定します。通常の `sfnx` 推論処理で読む設定ではありません。`fnx_run` は `src/split/CMakeLists.txt` で `split_fnx_run` として組み立てられる検証用ドライバーです（`src/split/CMakeLists.txt:153-162`）。

## 値と判定

| 環境変数の状態 | 使用するディレクトリ |
|---|---|
| 未設定 | `/tmp/fnx-lab-<実行ユーザーの UID>` |
| 設定あり（空文字を含む） | 値をそのまま使用。空文字の場合は後続の `"/" + ファイル名` との連結により `/` 直下のパスになる |

値の trim、正規化、存在確認、範囲検査はありません。CLI 引数による上書きもありません。既定パスは `getuid()` を使って実行ユーザーごとに分けられます。判定結果を cache せず `exact` 処理のたびに読みます（`src/split/tools/fnx_run.cpp:295-298,765`）。

## 有効になる条件

`fnx_run` が `exact [NAME]`（`NAME` 省略時は `try`）または `exact base` モードを実行するときに使われます。`lab_mode()` が `exact` を lab check に振り分け、その中で lab パスを選びます（`src/split/tools/fnx_run.cpp:437,746-769,960-982`）。`read`、`decode`、`batch`、`compare` 等は同じ lab check 関数内にありますが、`FNX_LAB_DIR` を使ったファイルパスを構成するのは `exact` 経路です。

## 実行時の詳細

`exact` は選択されたディレクトリに `<モデル名>-<NAME>[-<prompt>].lgr` を書き、同じ場所の `<モデル名>-base[-<prompt>].lgr` と比較します。`exact base` はまず `base-new` ファイル群を作成し、検証に失敗した場合は既存 base を置き換えません。全チェックに通ると base ファイルと identity ファイルを更新します（`src/split/tools/fnx_run.cpp:765-769,889-895,926-953`）。

ディレクトリの作成処理はありません。無効な場所、存在しないディレクトリ、書き込み不可などの失敗はファイル操作側で検出されます。`exact` で別ビルドの base identity が見つかると、標準出力に現在のディレクトリと専用ディレクトリの例（`FNX_LAB_DIR=/tmp/fnx-lab-...`）を含む案内を出して status 1 で戻ります（`src/split/tools/fnx_run.cpp:773-788`）。その他の例外は `fnx_run: <例外内容>` と stderr に出して status 1 になります（`src/split/tools/fnx_run.cpp:1364-1373`）。

## 根拠

- `src/split/tools/fnx_run.cpp:188-195` — lab checks と既定ディレクトリについての説明。
- `src/split/tools/fnx_run.cpp:295-298` — 唯一の値読み取り箇所と未設定時の既定値。
- `src/split/tools/fnx_run.cpp:437-459,746-769,889-953,960-982` — lab check の振り分け、パス構成、ファイル出力と base 更新。
- `src/split/CMakeLists.txt:153-162` — 検証ドライバー `split_fnx_run` のビルド定義。
