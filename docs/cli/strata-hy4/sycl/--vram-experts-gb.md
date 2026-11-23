# `strata-hy4-sycl --vram-experts-gb`

調査対象: Strata commit `b394b71292adf278b410d120592c773ba178e648`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-sycl` |
| コマンド | `strata-hy4-sycl`（トップレベル） |
| オプション | `--vram-experts-gb` |
| 別名 | なし |
| 値 | 浮動小数点数として `atof` で読み取る GiB 値 |

## 役割

HY4-SYCL runner が expert cache に割り当てる GPU メモリ予算を指定する。単体実行では主 GPU の VRAM expert cache の上限として使われ、複数 GPU を指定した場合は同じ正数値が各 peer GPU の上限にも個別に渡される。指定がない場合や負数の場合は環境変数または空き容量から自動決定する（`engine/src/hy4flash/sycl/sy_graph.h:127-150`）。

## 使い方

```sh
# 単体実行で expert cache 予算を 4 GiB に設定
strata-hy4-sycl --native model.strata --tokens tokens.txt --vram-experts-gb 4

# server モードでも同じ予算を設定
strata-hy4-sycl --serve --native model.strata --vram-experts-gb 4
```

## 値と既定値

- 値は `atof` で `double` に変換される。パーサーには数値形式・正値・上限を検証する処理がなく、無効な文字列は `atof` の結果（通常 `0`）として扱われる。重複指定時は後の値が前の値を上書きする（`engine/src/hy4flash/sycl/sy_main.cpp:107-115,140-141`）。
- 既定値は `-1.0`。負数は明示的な予算には使われず、自動決定分岐へ進む（`engine/src/hy4flash/sycl/sy_main.cpp:103,140`、`engine/src/hy4flash/sycl/sy_graph.h:127-139`）。
- 値は GiB を `1073741824` バイトとして変換される。主 GPU では `0` は VRAM cache の予算 0 となる。cache 初期化は少なくとも全レイヤー分の slot 容量がない場合に正常終了し、cache を無効化する（`engine/src/hy4flash/sycl/sy_graph.h:129-141`、`engine/src/hy4flash/sycl/sy_vram_cache.h:723-725`）。
- オプションの値を省略すると `nxt()` が `ERR --vram-experts-gb needs a value` を stdout に出し、終了コード 2 で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:109-115,140`）。

## 実行時の動作

parser は値を `vram_experts_gb` に格納し、server モードでは `ServeOpts` にコピーする。通常の単体実行と server のどちらも `setup_experts_unified` に渡され、主 GPU の expert cache の予算を決める（`engine/src/hy4flash/sycl/sy_main.cpp:140,226-248,298-305`、`engine/src/hy4flash/sycl/sy_serve.h:28-37,280-285`）。

- 値が `>= 0` の場合、主 GPU 予算を指定値（GiB）にする。
- 値が負数で `HY4S_VRAM_EXPERTS_GB` が設定されている場合、その環境変数を `atof` で読み、正数ならその値を使用し、0 以下なら予算 0 にする。
- 引数が負数で環境変数も未設定なら、GPU 全メモリの 94% を安全上限とし、既割当量と呼び出し元の予約量を差し引く。残りがその合計より 256 MiB を超えない場合、予算は 0 のままになる。
- 予算から workspace と expert slot 容量を差し引き、可能な slot 数を最大 1.4 GiB の slab 単位で確保する。実際の割当てが失敗した場合は、それまでに確保できた slab 数に留まる。slot が確保できると rank 順に expert データを読み込む（`engine/src/hy4flash/sycl/sy_vram_cache.h:728-750,752-798`）。
- `--gpus` / `--devices` 等で peer GPU があるとき、引数が正数ならその値を**各 peer GPU ごと**の予算として使う。0 または負数の場合は peer GPU ごとに自動予算（全メモリの 90% から workspace と 256 MiB を控除）になる。このため `--vram-experts-gb 0` は主 GPU cache を止める一方、peer GPU cache を自動予算にする場合がある（`engine/src/hy4flash/sycl/sy_graph.h:144-152`、`engine/src/hy4flash/sycl/sy_peer.h:182-186,231-259`）。

## 適用条件と副作用

この値は SYCL 版 `strata-hy4-sycl` の parser に属する。通常実行ではモデルのロード・初期化後に expert 配置を行い、server 経路でも server 初期化後に同じ配置関数を呼ぶ（`engine/src/hy4flash/sycl/sy_main.cpp:255-264,294-305`、`engine/src/hy4flash/sycl/sy_serve.h:267-285`）。cache の slab は GPU メモリに確保され、選択した expert 重みをファイルから読み込む。指定予算を超えて割り当てる保証はなく、GPU メモリ確保が失敗すれば部分的な slot 数になる（`engine/src/hy4flash/sycl/sy_vram_cache.h:736-750,769-798`）。

## 出力とエラー

- 主 GPU cache の初期化が成功して slot がある場合、stderr に `[vram-cache] ...` の slot 数、slab 数、実割当 GiB などを出力する。予算不足で cache が無効化された場合、この初期化ログは出ない（`engine/src/hy4flash/sycl/sy_vram_cache.h:723-725,750,796-798`）。
- expert 配置関数が失敗した場合、単体実行は stderr に `experts: <理由>` を出して終了コード 1、server はプロトコル出力に `ERR experts: <理由>` を出して終了コード 1（`engine/src/hy4flash/sycl/sy_main.cpp:304-306`、`engine/src/hy4flash/sycl/sy_serve.h:283-285`）。
- 確認したソースでは、数値が不正な場合に専用の validation error を出す経路は見つからなかった。`atof` の詳細な受理規則は C ライブラリ側の仕様となるため、本調査では Strata の独自挙動として扱わない。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:103-115,140` — 既定値、値の読み取り、値省略時のエラー。
- `engine/src/hy4flash/sycl/sy_main.cpp:226-248,298-309` — server 設定への転送と通常実行での expert 配置呼び出し。
- `engine/src/hy4flash/sycl/sy_serve.h:28-37,280-288` — server オプション保持と配置処理の呼び出し。
- `engine/src/hy4flash/sycl/sy_graph.h:123-153` — 引数・環境変数・GPU空き容量による予算決定、および peer GPU への予算転送。
- `engine/src/hy4flash/sycl/sy_vram_cache.h:690-798` — cache 初期化、予算不足時の無効化、GPU slab 確保、expert 読み込みとログ。
- `engine/src/hy4flash/sycl/sy_peer.h:182-259,286-364` — peer ごとの予算と自動算出、割当て、失敗経路。

環境変数 `HY4S_VRAM_EXPERTS_GB` の専用調査文書は、文書リポジトリで確認できなかった。
