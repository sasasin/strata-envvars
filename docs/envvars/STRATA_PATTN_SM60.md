# `STRATA_PATTN_SM60`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA の実験的 sm_60 ビルドで、対応する QSA の prompt attention を score / value カーネルで処理する opt-in スイッチです。int8 K/V の通常の decode attention と同じ計算順序を使う実装で、対象となる prompt の attention 経路を置き換えます。設定しただけで常に使われるわけではなく、prompt attention の既定経路が処理を断った後、GPU 世代・KV 形式・shape・scratch の条件を満たす場合だけ呼ばれます（`src/prefill/prefill.cpp:4076-4098`, `src/kernels/cuda/qsa_pattn.cu:402-449`）。

## 値と判定

`std::getenv` の結果を空文字でない場合に `std::atoi` へ渡し、整数値が 0 かどうかで判定します。文字列全体の厳密な検証はしません。

| 環境値 | 判定 | 対応ビルドでの結果 |
|---|---|---|
| 未設定 | 0 | 無効。既定の attention 経路を使う |
| 空文字 | 0 | 無効。既定の attention 経路を使う |
| `atoi` の結果が 0 | 0 | 無効。既定の attention 経路を使う |
| `atoi` の結果が非 0 | 非 0 | pattn 経路を要求する |

たとえば `1`, `-1`, `2`, `1junk` はそれぞれ非 0 として有効になります。`true` や `0junk` は `atoi` の結果が 0 なので無効です。先頭の空白や符号は `atoi` の規則で処理されます。非 0 の値そのものは強度として使わず、ログに整数値を出す以外は ON/OFF 判定に使います（`src/kernels/cuda/qsa_pattn.cu:34-50`）。

## 有効になる条件

pattn 実装のコンパイル条件は CUDA かつ `STRATA_EXPERIMENTAL_SM60` です。CMake では同オプションは既定 OFF で、ON のとき compile definition が追加されます（`src/kernels/cuda/qsa_pattn.cu:25-30`, `CMakeLists.txt:236-237,280-284`）。このビルド条件がない CUDA ビルドや HIP ビルドでは、環境値が非 0 でもカーネルはなく、通常経路に留まります。

対応カーネルがビルドされていても、次の条件を満たさなければ `qsa_pattn_batch` は `false` を返し、呼び出し側が decode attention の通常ループを実行します。

- カレント GPU の compute capability major が正確に 6（sm_60 / 6.1）。sm_70 以上や 6 未満では使いません（`src/kernels/cuda/qsa_pattn.cu:402-405,378-398`）。
- K と V が int8 で、両方の scale と page table があり、Q4 / hybrid Q4 pool ではないこと（`src/kernels/cuda/qsa_pattn.cu:412-415`）。
- `head_dim == 256`、`n_head == 12 * n_head_kv`、正の `cap`、必要な入力・scratch があること（同:412-415）。
- `ceil(cap / 64) <= 33`、すなわち `cap <= 2112` であること。さらに scratch に少なくとも 1 query 分の領域があること（同:417-424）。

prompt attention の既定関数が先に成功すると、この変数の判定や pattn 関数の呼び出しには進みません。`STRATA_PROMPT_ATTN_OLD` は値でなく設定有無で既定経路を強制し、その経路が pattn の判定へ進む契機になりますが、pattn 自体を有効にはしません（`src/prefill/prefill.cpp:4080-4091`）。

## 実行時の詳細

`pattn_mode()` 内の function-local `static const int` が初回評価時に値を読み、その後プロセス内で再評価しません。したがって最初の判定後に環境を変更しても反映されません。環境値は prompt の QSA attention 分岐で既定関数が失敗した場合（または `STRATA_PROMPT_ATTN_OLD` が設定されている場合）に初めて調べられます（`src/kernels/cuda/qsa_pattn.cu:34-50`, `src/prefill/prefill.cpp:4080-4098`）。

対応ビルドで非 0 なら stderr に `strata pattn: STRATA_PATTN_SM60=<値>: ...` と出し、要求を許可します。その後、上記の GPU / pool / shape / scratch 条件に合えば query batch ごとに score kernel と value kernel を起動します。条件不一致で `false` が返った場合、追加の理由ログはなく、呼び出し側は `qsa_decode_attn_batch` を `m.attn_batch` 単位で実行します（`src/kernels/cuda/qsa_pattn.cu:41-43,402-437`, `src/prefill/prefill.cpp:4087-4098`）。

非対応ビルドで非 0 なら stderr に `strata pattn: STRATA_PATTN_SM60 is set, but this build has no sm_6x kernels (CUDA with STRATA_EXPERIMENTAL_SM60 only); the usual attention runs` と出して無効にします。0 の場合はこの警告も出しません（`src/kernels/cuda/qsa_pattn.cu:38-47`）。カーネル起動エラーを `cudaGetLastError()` が検出した場合は、最初の一度だけ `strata pattn: launch failed (<CUDA error>); the usual attention runs instead` を stderr に出し、通常ループへ戻します（同:438-447）。

この経路は `src/prefill/prefill.cpp` から呼ばれる prompt path のもので、decode path の切り替えではありません。`docs/OLDER_GPUS.md` は作者の測定として GP100 1 die・26K context の 1,536-query chunk で QSA layer あたり 43.3→30.8 ms、4 dies の 8K–150K token prompt で 2–3%短縮と記しますが、同資料はこの値を作者の測定として紹介し、Strata 側では未測定としています（`docs/OLDER_GPUS.md:170-177`）。

## 根拠

- 環境変数の唯一の実読み取り、変換、static cache、ビルド差、ログ: `src/kernels/cuda/qsa_pattn.cu:25-50`。
- prompt path からの分岐、既定 attention・pattn・通常 attention へのフォールバック: `src/prefill/prefill.cpp:4076-4099`。
- GPU 世代判定と shape / KV / scratch / launch 条件: `src/kernels/cuda/qsa_pattn.cu:378-398,402-449`。
- ビルドオプション: `CMakeLists.txt:236-237,280-284`。
- 既存の説明とその測定の帰属: `docs/OLDER_GPUS.md:170-177`。
