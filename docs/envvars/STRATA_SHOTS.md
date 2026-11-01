# `STRATA_SHOTS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象の作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

`apps/host/scripts/motion.mjs` が作る motion 診断用の動画フレームと contact sheet の保存先ルートを指定します。通常の Strata アプリや engine の実行設定ではなく、UI 開発・診断用スクリプトの出力先です。同スクリプトは `apps/host/package.json` の `npm run motion` から起動できます。

## 値と判定

| 状態 | `ROOT` の値 | 動作 |
|---|---|---|
| 未設定 | `resolve('.shots')` | 実行時の作業ディレクトリ直下の `.shots` を使う |
| 設定あり（空文字を含む） | `resolve(環境変数の文字列)` | 指定文字列を作業ディレクトリ基準で絶対パスに解決して使う |

値の数値変換、文字列比較、空文字の除外、存在確認や範囲検証はありません。JavaScript の nullish coalescing (`??`) なので、空文字は fallback の `.shots` に置き換わらず、`resolve('')` の結果である作業ディレクトリが保存先になります。相対パスは作業ディレクトリ基準、絶対パスはそのまま解決されます。

## 有効になる条件

- `apps/host/scripts/motion.mjs` を Node.js で実行したときだけ評価されます。パッケージスクリプトは `npm run motion`（同じ package の `scripts/motion`）です。
- スクリプト冒頭で `ROOT` を一度決めます。起動後に環境変数を変えても再評価されません。
- `STRATA_URL` は別の設定で、ページを開く URL の base を指定します。`STRATA_SHOTS` との優先順位や連動はありません。
- ソースコメントによると、この診断スクリプトは開発サーバーとキャッシュ済み Chromium を必要とします。Chromium が見つからない場合は `No cached Chromium found.` を stderr に出し、終了コード 2 で終了します。これは `STRATA_SHOTS` の値判定ではありません。

## 実行時の詳細

モジュール読み込み時に `ROOT` を解決し、その下に `motion-frames` を再帰的に作成します。各 interaction の開始時には `motion-frames/<name>` を再帰削除してから作り直し、動画と抽出フレームを置きます。フレームが得られた場合は `ROOT/motion-<name>.png` に contact sheet を保存します。したがって既定の出力先は `.shots/motion-<name>.png` です。

ディレクトリ作成はエラーハンドリングのない初期化処理です。指定先に作成できないなど `mkdirSync` が失敗すると、その例外でスクリプトは中断します。各 clip の既存 `motion-frames/<name>` は `rmSync(..., { recursive: true, force: true })` で削除されます。環境変数値自体の警告やログ出力はありません。スクリプトの最終結果は motion 検査の成功・失敗を表示し、失敗があれば終了コード 1 になります。

## 根拠

- `apps/host/scripts/motion.mjs:25-29` — `STRATA_SHOTS` を `process.env` から一度読み、既定値 `.shots` と組み合わせて `resolve()` し、`motion-frames` を作成。
- `apps/host/scripts/motion.mjs:3-16,41-44` — 診断用途、dev server / cached Chromium の要件、および Chromium 不在時の stderr と終了コード。
- `apps/host/scripts/motion.mjs:50-54,74-96` — clip ごとの出力ディレクトリの削除・作成、動画とフレームの取り扱い。
- `apps/host/scripts/motion.mjs:103-123` — contact sheet を `ROOT` 直下へ保存し、成功時に出力パスを表示。
- `apps/host/scripts/motion.mjs:285-294` — motion 検査の結果表示と終了コード。
- `apps/host/package.json:7-21` — `motion` パッケージスクリプト。
- `apps/host/.gitignore:1-7` — `.shots/` が ignore 対象。

調査では `STRATA_SHOTS` の全参照を検索し、実際の環境読み取りは `apps/host/scripts/motion.mjs:27` のみと確認しました。C++/CUDA/HIP/SYCL engine、サーバー本体に同名変数を読む箇所はありません。関連する `docs/DETAILS.md` にこの変数の説明は見つかりませんでした。
