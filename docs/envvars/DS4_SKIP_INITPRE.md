# `DS4_SKIP_INITPRE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek V4.1 の Metal 実装で、ウィンドウ入力用の `pre` バッファ初期化を飛ばす診断・調査用スイッチです。`init_pre()` は各行につき 8 要素を `[1, 0, 0, 0, 0, 0, 0, 0]` に設定します。この環境変数が有効だと、その書き込みを行わず呼び出し元へ戻ります。

## 値と判定

`ds4_dbg("DS4_SKIP_INITPRE")` は値を変換せず、環境変数が存在するかだけを見ます（`getenv(name) != nullptr`）。したがって、未設定なら無効、設定されていれば有効です。空文字、`0`、`false` を含め、設定値の内容は区別されません。

判定は `init_pre()` が呼ばれるたびに行われ、static cache はありません。

## 有効になる条件

- `STRATA_METAL` でビルドされた DeepSeek V4.1 エンジンでのみ有効です。非 Metal ビルドの `ds4_dbg()` は常に `false` を返す `constexpr` 関数で、環境を読みません。
- CLI 引数、他の環境変数、設定値との優先順位や上書きはありません。
- Metal の通常の逐次 forward に加え、MTP、chunk、複数デバイス経路から呼ばれる `init_pre()` に適用されます。対象関数の分岐は共通です。

## 実行時の詳細

Metal では `init_pre()` の冒頭でこの変数を調べ、設定されていれば直ちに return します。そのため、通常行う `metal_host::init_pre()` による初期化も、同関数が処理しなかった場合の `init_pre_kernel` 起動もスキップされます。通常の初期化では `pre[0..T*8)` に各トークン行の固定パターンを書き込みます。

このバッファは後続の `hc_pre_norm()` が読みます。変数を設定した場合、Strata は `pre` の既存内容を変更・検査せず後続処理へ進むため、その内容が新規に初期化済みである保証はありません。ソース上、この分岐自体による警告・ログ・エラー終了はありません。結果の数値や生成内容への影響はソースだけでは特定できません。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — `ds4_dbg` の定義。Metal では引数名を `getenv` に渡し、非 Metal では常に false。
- `src/dsv41/ds4_kernels.cu:1712-1715,2176-2184` — `init_pre_kernel` の固定パターン、Metal 限定の早期 return、その後の Metal host 初期化と kernel fallback。
- `src/dsv41/ds4_model.cu:7785,7810-8117` — 通常 forward で初期化し、後段の正規化処理に使用。
- `src/dsv41/ds4_model.cu:8636,8672-8680,8809,8874-8883` — chunk 経路での初期化と後続利用。
- `src/dsv41/ds4_model.cu:9790,9900,10061-10062` — serial / device-group 経路での初期化と後続利用。
- `docs/DEEPSEEK_MAC.md:97-98` — 公開されている診断変数の例。この文書には `DS4_SKIP_INITPRE` の説明はありません。
