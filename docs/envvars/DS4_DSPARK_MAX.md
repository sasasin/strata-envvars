# `DS4_DSPARK_MAX`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DS4.1 エンジンの DSpark speculative decoding で、1ラウンドに後続の検証へ渡す draft の最大数を指定します。ドラフト計算の後、`out` と対応する confidence 配列を同じ数だけ先頭から残します。0以下ならこの環境変数による上限処理は行いません。

## 値と判定

`DS4_DSPARK_MAX` が設定されていると、`std::atoi` で整数に変換します。文字列全体の妥当性検査やエラー通知はありません。先頭の空白や符号を含む整数接頭辞は変換され、整数として読めない文字列（空文字を含む）は `atoi` の結果0になります。たとえば `3tail` は3、`-2` は-2、`tail` と空文字は0として扱われます。

| 状態 | `max_drafts` | 挙動 |
|---|---:|---|
| 未設定 | 0 | 環境変数による切り詰めなし。`--dspark-block N` が正ならその値が上限になる |
| 整数変換結果が正 | その値 | 1ラウンドの draft 数をその値までに切り詰める |
| 空文字、非数値、0、負数 | 0以下 | 切り詰めなし。環境変数が設定済みなので `--dspark-block` にも置き換わらない |

変換結果が実際の draft 数以上なら配列の変更はありません。値がpackのDSpark block sizeより大きくても、pack側で生成できる数を増やす働きはありません。

## 有効になる条件

- DS4.1 の `Model::Impl` の処理で参照されます。他のStrataエンジンや外部ライブラリの設定として使われる根拠はありません。
- DSpark draft が実際に呼ばれるには、DSpark block がロードされており、`draft_()` 内のモデル状態・context条件も満たす必要があります。たとえば `g.n_mtp == 0`、block size `T < 1`、または現在位置とblock sizeの合計が最大contextを超える場合、`draft_()` は候補を作らず正常終了します。
- `--dspark off` / `--dspark none` や `--dspark auto` の容量判定でDSparkが無効になると、環境変数に正の値があっても候補は生成されません。
- コマンドラインの `--dspark-block N` は `N` が正で、かつ `DS4_DSPARK_MAX` が未設定の場合に限って上限として使われます。環境変数を空文字や不正値で設定した場合も「設定済み」のため、このCLI値を抑止します。

## 実行時の詳細

環境変数は `Model::Impl` の生成時に一度 `getenv` され、その結果がメンバー `max_drafts` に保存されます。続く `load()` では、環境変数が未設定で `--dspark-block` が正の場合だけ `max_drafts` をCLI値で上書きします。モデルをロードした後の環境変更を再読込する処理はありません。

各ラウンドの `draft()` はまず `draft_()` を実行し、成功・失敗にかかわらず、`max_drafts > 0` かつ出力数が上限を超えていれば `out` と `conf` を同じ長さに縮めます。これはドラフト計算後の候補列の切り詰めであり、ドラフト計算そのものの早期終了や候補の再生成は行いません。切り詰め後の候補が検証処理へ渡ります。環境変数固有のログ、警告、エラーはこの処理にはありません。

## 根拠

- `src/dsv41/ds4_model.cu:800-801, 911-919`: `Model::Impl` と環境変数の読み取り・`atoi` 変換。
- `src/dsv41/ds4_model.cu:2022-2035`: `load()` におけるDSparkの自動無効化、未設定時だけの `--dspark-block` 適用。
- `src/dsv41/ds4_model.cu:6715-6733`: 各roundの `draft()` と、候補およびconfidence配列の切り詰め。
- `src/dsv41/ds4_model.cu:6735-6742`: DSpark block/context条件による空候補での正常終了。
- `src/dsv41/ds4_main.cpp:1224-1234`: `--dspark` と `--dspark-block` のCLI値の設定。
- `src/dsv41/ds4_model.cu:9352-9354`: `Model` 生成時に `Impl` を作成し、その後 `load()` を呼ぶAPI構造。
- `docs/MODELS.md:101` はDSparkの測定について説明しますが、`DS4_DSPARK_MAX` の値域や上限動作の記載はありません。性能値はこの環境変数の効果として扱っていません。
