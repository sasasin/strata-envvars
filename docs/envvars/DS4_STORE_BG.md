# `DS4_STORE_BG`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DSv41 の RAM expert store について、プロファイル上の高頻度 expert をモデルロード時にどこまで同期して preload し、残りをバックグラウンドで読むかを切り替えます。通常は候補をすべて同期 preload します。有効にすると先頭約 48 GB 相当だけを同期で読み、残りを専用スレッドで読みます。

これはサーバー起動時のモデルロード/preload 経路に関する設定です。モデルロード後の各リクエストで設定を読み直すコードはありません。

## 値と判定

値は `std::atoi()` で整数に変換し、変換結果がちょうど `1` かを判定します。文字列全体の妥当性検査はありません。

| 値 | 判定 | 動作 |
|---|---|---|
| 未設定 | 無効 | プロファイル候補をすべて同期 preload |
| `1` | 有効 | 先頭約 48 GB 相当を同期 preload、残りをバックグラウンド preload |
| `01`, `+1`, ` 1`, `1abc` | 有効 | `atoi()` の結果が 1 になるため上記と同じ |
| 空文字、`0`, `2`, `true`, `abc` | 無効 | 同期 preload のみ |

大文字小文字や空白の独自処理はありません。空文字は `atoi()` で 0 になります。

## 有効になる条件

環境変数の判定が有効でも、RAM store が作られない経路では効果がありません。`init_store()` はストア容量が正、モデルの layer が存在し、先頭 layer の形式が MXFP4 で、expert がファイルから読む経路である場合に限りストアを初期化します。初期化失敗時は `store` が設定されず、`preload_store()` は何もしません。

また、`DS4_STORE_PRELOAD` が設定され `atoi()` の結果が 0 の場合、`preload_store()` が先に return するため `DS4_STORE_BG` は参照されません。プロファイルの合計カウントが 0 の場合も preload せず、最初の token の処理でプロファイルが作られる想定です。同期 preload の候補数が 48 GB 相当以下なら残りがなく、バックグラウンドスレッドは起動しません。

## 実行時の詳細

モデル初期化では `init_store()` の直後に `preload_store()` を呼びます。`preload_store()` はモデル trunk の各 layer を走査し、VRAM 常駐ではなく、プロファイルカウントが正の expert だけを集めます。候補は `プロファイルカウント / expert blob サイズ` の降順に安定ソートされます。

`DS4_STORE_BG` が有効でない場合、候補リスト全体を `store->preload()` に渡します。有効の場合、同期分の候補数を `min(候補数, 48e9 / max(1, L[0].blob))` として、その先頭部分だけを同期で読みます。残りは `store_bg` スレッドが最大128 expertずつ `store->preload()` に渡します。スレッドは各 piece の前に `quit` を確認し、モデル破棄時に join されます。

stderr には同期分について `ds4: RAM store: ... read in ...` と表示され、非同期分が残る場合は末尾に `; the rest is read in the background` が付きます。バックグラウンド処理が完了すると `ds4: RAM store: ... read in the background in ...` が出ます。

`docs/DETAILS.md` にはこの変数の説明を確認できませんでした。実装コメントには特定の R9700 環境での起動時間・prompt 待ち・decode 差の測定メモがありますが、条件を一般化できる資料ではないため、性能値としては記載していません。

## 根拠

- `src/dsv41/ds4_model.cu:2821-2823` — モデル初期化時の `init_store()`、`preload_store()` 呼び出し順。
- `src/dsv41/ds4_model.cu:1234-1256` — 終了時の `quit` 設定と `store_bg` の join。
- `src/dsv41/ds4_model.cu:4633-4642` — store 初期化条件と自動容量処理。
- `src/dsv41/ds4_model.cu:4710-4715` — store の初期化失敗時の扱い。
- `src/dsv41/ds4_model.cu:4748-4796` — preload 条件、プロファイル候補、環境変数判定、同期/非同期読み込みとログ。
