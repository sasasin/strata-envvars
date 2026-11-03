# `DS4_BORROW`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek 4.1 (DS4) GGUF の prompt 処理中、expert 用に確保した GPU メモリ領域の一部を prompt buffer として一時的に貸し出すかを選びます。借りた領域に重なる expert slot は prompt の chunk 実行中に通常の VRAM resident slot としては使わず、chunk 終了後に必要な expert を読み戻します。対象は `src/dsv41/ds4_model.cu` の DS4 実装です。

## 値と判定

`one_gpu_or("DS4_BORROW")` は `getenv` の値を `atoi` に渡し、0 以外なら有効、0 なら無効とします。文字列全体の検証はありません。

| 値 | 判定 |
| --- | --- |
| 未設定 | Metal build では無効。それ以外では `devs.size() == 1` のとき有効 |
| `0`、空文字、数値に変換できない文字列（例 `true`） | 無効（`atoi` が 0） |
| 0 以外に変換される文字列 | 有効。例 `1`, `2`, `-1`, `1tail` |

明示設定時は GPU 数や Metal の既定値より `atoi(value) != 0` の結果が優先されます。範囲チェックや clamp はありません。`atoi` のため、先頭の空白と符号は変換規則に従い、数字の後ろの文字列は検査されません。実装根拠は `src/dsv41/ds4_model.cu:1993-2007` です。

## 有効になる条件

値判定が有効でも、実際に貸し出しを設定するには `file_experts` が真で、`DS4_FLOW` が有効である必要があります。さらに各 GPU の chunk は、その GPU 上の trunk layer が単独配置（`l.nm == 1`）かつ MXFP4 format で、expert slot の stride が正の場合だけ貸し出し対象になります。これらを満たさない GPU の chunk は自分の buffer 領域を確保します（`src/dsv41/ds4_model.cu:4043-4047,4109-4124`）。

`DS4_FLOW` は未設定なら有効、設定されていれば `atoi(value) != 0` で判定されます。従って空文字や非数値文字列は無効です。これは独立した条件であり、`DS4_BORROW=1` だけでは flow を有効化しません（`src/dsv41/ds4_model.cu:3660-3676,3993-3997,4043-4047`）。flow 自体も file experts の場合に準備され、各 GPU の全 trunk layer が MXFP4 などの条件に合うと `Chunk::flow` が立ちます（`src/dsv41/ds4_model.cu:3681-3706`）。

`file_experts` は GGUF expert をファイルから扱う経路に関係します。初期化コードでは、RAM に expert をコピーする必要があるかを `file_experts` として判定し、コメントでは GGUF で `--mmap-experts off` の場合にコピーすると説明しています（`src/dsv41/ds4_model.cu:2758-2776`）。モデル形式、配置、layer format が適合しない場合は、環境変数が有効でも貸し出しません。

## 実行時の詳細

`DS4_BORROW` は static cache ではなく、helper が呼ばれるたびに環境を読みます。初期化では chunk の既定値計算と chunk buffer 構築で判定します。chunk 既定値の拡大は `--prefill-chunk` が未指定で、初期 chunk が正、GGUF/file experts/flow が有効、かつ各 group に複数 member がない場合に限り、GPU の空き領域と RAM の上限を調べて候補 32K または 16K を選びます。条件不成立や容量不足なら渡された既定 chunk `c0` を返します（`src/dsv41/ds4_model.cu:3993-4024`; 呼び出しと CLI override の位置: `src/dsv41/ds4_model.cu:2788-2796`）。`DS4_CHUNK` が設定されれば chunk をその値で上書きするため、この既定値調整は通りません。

buffer 構築時に `borrow_on` が真で layer 条件も合うと、`Chunk::borrow` が設定され、prompt buffer を expert allocation の末尾領域に配置します。実行する chunk の buffer が貸し出し領域に収まるか確認し、領域を一時的に prompt buffer として使います。chunk 実行の終了時には RAII cleanup が `borrow_end()` を呼び、領域下にあった expert を必要に応じて読み戻して cache を再利用できる状態にします（`src/dsv41/ds4_model.cu:4120-4124,12621-12655,12952-12957,12688-12708`）。

貸し出し分を除いた expert 用空き領域が prompt buffer 必要量の 2 倍未満なら、実装は貸し出しを取り消して prompt 用の独立 buffer を確保します。`--verbose` 時には `ds4: CUDA%d keeps the prompt path's room for itself ...` を stderr に出します（`src/dsv41/ds4_model.cu:5372-5392`）。expert slot 数が少なく chunk を収められない場合は `ds4: CUDA%d keeps too few experts in VRAM ...` を stderr に出し、chunk を無効化します。slot 数に合わせて chunk を縮めた場合も stderr に結果を出します（`src/dsv41/ds4_model.cu:5494-5524`）。verbose 時には貸し出す VRAM 量と chunk 上限も記録します（`src/dsv41/ds4_model.cu:5541-5543`）。

prompt 実行開始時に借用領域がない、flow stream がない、または buffer が領域を超える場合は `borrow_begin()` が `err` を設定して失敗を返します（`src/dsv41/ds4_model.cu:12624-12639`）。本調査では、その呼び出し元より上位でこのエラーを最終的に表示する箇所までは追っていません。

## 根拠

- 値判定と OS/backend 別既定値: `src/dsv41/ds4_model.cu:1990-2007`
- file experts と prompt chunk の選択: `src/dsv41/ds4_model.cu:2758-2796`
- flow 判定と準備条件: `src/dsv41/ds4_model.cu:3660-3706,3993-4024`
- borrowed buffer の構築と layer 条件: `src/dsv41/ds4_model.cu:4043-4047,4109-4124`
- 容量不足時の fallback / slot 数による chunk 調整: `src/dsv41/ds4_model.cu:5372-5392,5494-5543`
- chunk 実行中の借用と終了時の返却: `src/dsv41/ds4_model.cu:12621-12655,12688-12708,12952-12957`
