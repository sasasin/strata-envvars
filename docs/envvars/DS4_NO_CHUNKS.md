# `DS4_NO_CHUNKS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`STRATA_METAL` を定義してビルドした DeepSeek V4.1 実装で、prompt 用の chunked（layer-major）経路を既定で選ぶ処理を抑えます。変数名とは違い、値を `1` にして chunk を禁止するのではなく、環境変数が設定されているかどうかで既定の `prompt_par` 上書きを止めます。`prompt_par` が false になるとは限らず、chunk 数 `chunk` を直接設定する変数でもありません。

この読み取りは `src/dsv41/ds4_model.cu` の `#if defined(STRATA_METAL)` 内に1箇所だけあります。CUDA/HIP 等でこの macro が定義されないビルドでは、この変数は Strata から読まれません。

## 値と判定

値の変換や文字列比較はありません。`std::getenv("DS4_NO_CHUNKS") == nullptr` という設定有無だけを見ます。

| 状態（`STRATA_METAL` ビルド） | この分岐の処理 |
|---|---|
| 未設定 | `prompt_par = true` にする |
| 空文字を含む、何らかの値が設定済み | `prompt_par` を変更しない |

したがって `DS4_NO_CHUNKS=0`、`=1`、任意の文字列、空文字はいずれも同じ扱いです。設定済みでも chunked prompt が無効になるのは、その前段の条件で `prompt_par` が false であり、後続の chunk サイズ決定でも `chunk` が正にならない場合に限られます。

## 有効になる条件

- `#if defined(STRATA_METAL)` のビルドでのみ分岐がコンパイルされます。
- `prompt_par` の通常値は、`--threads` または `tp > 1` なら true。それ以外では `--prefill-chunk` と `DS4_WINDOWS` の組み合わせから決まります。`--prefill-chunk` が正、または未指定時の既定 chunk が有効で、かつ `DS4_WINDOWS` が未設定なら true です。
- Metal 分岐はこの通常値の後で評価されます。変数が未設定なら通常値にかかわらず `prompt_par` を true に上書きします。変数が設定済みなら通常値を維持するだけで、false への強制はしません。そのため `--threads` / `--tp` による true は、`DS4_NO_CHUNKS` 設定済みでも残ります。
- `chunk` は別に決まり、`prompt_par` が true の場合に `--prefill-chunk` の値（0以上）または既定値を使います。`--prefill-chunk 0` は chunk を0にするため、`prompt_par` が true でも実際の chunk 実行は行いません。`DS4_CHUNK` が設定されている場合は、`prompt_par` が true ならその `atoi` 値で `chunk` を上書きし、false なら0にします。
- chunk が正でも、モデル内の expert 型に chunk 用 GPU kernel がない場合は0に戻されます。chunk 用バッファが確保できない場合は chunk を段階的に小さくし、最小でも確保できなければ windows 経路に戻ります。

## 実行時の詳細

値は `Impl::load` 内の prompt 経路選択中に読み取られます（モデル読み込み時）。`static` cache はなく、同じプロセスで別の load があればその時点の環境を再評価します。一度ロードしたモデルの後続 prompt ごとに読み直す処理はありません。

未設定時に `prompt_par` を true にすると、後続の `chunk` 決定が正の値を与える場合、prompt の長い入力は `chunk_min` 以上で chunked 経路を利用できます。`Model::feed` は `chunk > 0 && n >= chunk_min` のとき `forward_chunks` または `feed_windows` を選びます。これは prompt の経路選択であり、コメントにもある通り decode の host-routed 経路はこの設定で変更しません。

変数そのものを名指しするログ、警告、エラー、終了経路はありません。後続処理では windows 実行時に `ds4: prompts run in windows of ...`、chunk 設定時に `ds4: prompt path: the chunked pass from ...` を stderr に出します。未対応型では chunk 経路を使わない旨を出し、確保失敗では小さい chunk を試し、最終的に windows へ戻った場合も理由を stderr に出します。

## 根拠

- `src/dsv41/ds4_model.cu:2223-2233` — `par`、CLI / `DS4_WINDOWS` による通常の `prompt_par` 判定と、Metal 限定の `DS4_NO_CHUNKS` 読み取り。
- `src/dsv41/ds4_model.cu:2293-2312` — `chunk` の決定、`DS4_CHUNK` による上書き、および windows 経路のログ。
- `src/dsv41/ds4_model.cu:2430-2436` — chunk 用 kernel がないモデルで chunk を無効化する経路。
- `src/dsv41/ds4_model.cu:2945-2999` — chunk バッファの確保、縮小、windows への fallback とログ。
- `src/dsv41/ds4_model.cu:3178-3205` — chunk の有無に応じた worker 起動とロード後処理。
- `src/dsv41/ds4_model.cu:10702-10715` — prompt 入力ごとの `chunk` / `chunk_min` に基づく実行経路。
- `docs/envvars/000_envvers.md:243` — 候補一覧に名前があることを確認。`docs/DETAILS.md` には `DS4_NO_CHUNKS` の説明は見つからず、上記の実装を裏付ける別の説明資料は確認できませんでした。
