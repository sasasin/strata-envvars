# `STRATA_GDN_CHUNKED`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

prompt の gated DeltaNet (GDN) recurrence を token ごとの通常 kernel から chunk 化した kernel に切り替える。CUDA は FP32 の prep/scan 経路、HIP は gfx11/gfx12 の WMMA 経路を選ぶ。対象のプロンプト chunk が短い、GPU 条件を満たさない、または必要な scratch を確保できないときは通常 recurrence に戻る。CUDA の実装は `src/prefill/kernels.cu:1230-1281, 3113-3190`、HIP の実装は同ファイル `:2137-2172, 3011-3025` にある。

## 値と判定

| 経路 | unset / 空文字 | chunk 化を選ぶ値 | 選ばない値 |
|---|---|---|---|
| CUDA（HIP でない build） | off | `atoi(value) != 0`。例: `1`, `2`, `-1`, `1tail` | `0`, `0tail`, `true`, `false`, 空文字 |
| HIP、gfx11 | `-1` として扱い off | `atoi(value) != 0`。例: `1`, `2`, `-1`, `1tail` | `0`, `0tail`, `true`, `false`, 空文字 |
| HIP、gfx12 | 自動判定。通常は 30,000 token 以上で選択。Linux かつ検査対象の全 GPU が gfx12 なら、通常起動時に未設定変数へ `1` が注入され、64 token 以上で選択 | 正の `atoi(value)`。例: `1`, `2`, `1tail`。負数は自動判定扱い | `0`, `0tail`, `true`, `false`。ただし unset/空文字は自動判定に戻る |

CUDA の本番 dispatch は `std::getenv` の結果を `std::atoi` に渡し、その結果が 0 でなければ有効とする。数値全体の検証、空白や大文字小文字の検査はない。`atoi` が数値 prefix を読める `1tail` は 1、数値 prefix がない `true` は 0 になる。`1` と `2` は有効化の点では同じで、`atoi(value) >= 2` のときだけ追加で 128-SM 条件を免除する（後述）。判定は関数内 `static` に保存される。`src/prefill/kernels.cu:1251, 3116-3118`。

HIP は `gdn_chunked_env()` が unset または空文字を `-1` に変換し、それ以外を `atoi` する。従って空文字と未設定は同じ自動判定扱いだが、`0` は明示的 off。数値 prefix のない文字列は `atoi` により 0 となる。負値も `-1` 以下の自動判定扱いで、正値は明示的 on。`1tail` は 1、`2tail` は 2 として扱われる。値は関数内 `static` に一度だけ読み込まれる。`src/prefill/kernels.cu:1836-1838, 2155`。

## 有効になる条件

- **CUDA:** 通常 dispatch (`variant` が 0/1、かつ serial recurrence でない経路) で `T >= 128` のとき chunked recurrence を試す。`STRATA_GDN_TC` が有効で TC 経路が成功すると、そちらが先に選択される。chunked 経路が選択されない、または使えない場合は key-head / pipelined / columns の通常 kernel に進む。`src/prefill/kernels.cu:3011-3025, 3110-3122, 3160-3188`。
- CUDA の chunked kernel は compute capability major 8 以上、十分な opt-in shared memory、scratch 確保が必要。既定では少なくとも 128 SM が必要で、少ない GPU では使わず caller が通常 kernel に fallback する。`STRATA_GDN_CHUNKED` の `atoi` 結果が 2 以上なら SM 数検査だけを飛ばす。compute capability と shared memory の検査、scratch 確保は残る。`src/prefill/kernels.cu:1235-1257, 1248-1255`。
- **HIP:** device が WMMA 対応の gfx11 または gfx12、`T >= 64`、出力 stride `ld16` が 8 の倍数であることが必要。通常 recurrence の variant 0/1 で試し、`STRATA_GDN_REC_HEADS` が設定され serial 経路になる場合は使わない。gfx11 は unset/空文字では off。gfx12 は unset/空文字のとき `STRATA_GDN_CHUNKED_MIN`（未設定・空文字なら 30000）以上の chunk に限り自動で使う。明示的な非ゼロ値では gfx12 の 64 token 下限を使う。`src/prefill/kernels.cu:1826, 1840-1843, 2137-2155, 3011-3025`。
- HIP の unset/空文字 gfx12 自動経路は `STRATA_GFX12_DEFAULTS` の先頭文字が `0` の場合に止まり、`STRATA_GDN_CHUNKED_MIN` が下限を変える。下限は `atoll` で読み、数値全体の検証や clamp はない。どちらも初回読み取り時に `static` cache される。`src/prefill/kernels.cu:1840-1843`。
- HIP build の `generate` 起動時、Linux かつ GPU 数を取得できて 1 台以上あり、調査ループが見る GPU（device index 0..63）がすべて gfx12 と判定され、変数が未設定なら `apply_gdn_chunked_default` がプロセス環境へ `STRATA_GDN_CHUNKED=1` を設定する。明示値（空文字も含む）があれば上書きしない。Windows ではこの既定値を設定しない。`src/program/generate.cpp:4074-4107`, `src/core/arch_defaults.cpp:278-290, 218-223`。
- この注入条件は `STRATA_GFX12_DEFAULTS` を確認しない。そのため Linux の全 gfx12 構成では `STRATA_GFX12_DEFAULTS=0` だけでは注入された `STRATA_GDN_CHUNKED=1` を止めず、明示的な `STRATA_GDN_CHUNKED=0` が必要。一方、注入されない gfx12 の unset/空文字自動経路では `STRATA_GFX12_DEFAULTS=0` が抑止する。起動ログの条件も unset かつ gfx12 defaults が有効な場合に限る。`src/core/arch_defaults.cpp:278-290, 344-347`; `src/prefill/kernels.cu:1840-1843`。
- HIP gfx12 では `STRATA_GDN_FUSE` が unset または `atoi != 0` なら、別の fused entry point も chunked mode のときに畳み込みと recurrence をまとめる候補になる。これは gfx12・64 token 以上などの条件を満たす場合だけで、失敗時には呼び出し元が個別 entry point を実行する。`STRATA_GDN_FUSE=0` はこの融合だけを止め、通常の chunked recurrence 判定とは別。`src/prefill/kernels.cu:2177-2198, 3223-3231`。

## 実行時の詳細

CUDA の選択は GDN recurrence dispatch 時に行う。`chunked` と `any_sms_env` は各関数内の `static` 値なので、最初の読み取り後にプロセス環境を変更しても反映されない。chunked kernel は 32 token 単位の prep と scan を scratch 上で実行する。失敗時は何も launch せず、通常 dispatch が後続の kernel を選択する。`src/prefill/kernels.cu:1230-1281, 1251-1255, 3116-3188`。

HIP の `gdn_chunked_env`、gfx12 自動下限、gfx12 defaults 判定も初回値を `static` cache する。GPU architecture の判定は thread ごとに直近 device を cache し、device が変われば取り直す。WMMA recurrence は chunked prep/scan を launch し、output norm を scan 側に含める。条件を満たさない場合は `false` を返し、既存経路が実行される。`src/prefill/kernels.cu:1836-1843, 2137-2172, 2177-2198, 3020-3024`。

## ログと測定値

gfx12 の architecture defaults 適用時、環境変数が未設定で `STRATA_GFX12_DEFAULTS` の先頭文字が `0` でない場合、stderr に `strata: RDNA4 (gfx12): prompt chunks of 30,000+ tokens use the chunked GDN scan (STRATA_GDN_CHUNKED=0 turns it off)` を出す。値が設定済みならこの行は抑制される。Linux 全 gfx12 の注入後も抑制される。通常の CUDA / HIP dispatch は、この変数の有効・無効だけを報告するログを出さない。`src/core/arch_defaults.cpp:344-347`, `src/program/generate.cpp:4091-4107`。

CUDA の診断用 probe がある場合、chunked 経路が使えなかった理由として scratch allocation、compute capability、SM 数、shared memory などを `reason` に記録する。ただしこれは通常起動ログではなく probe 用である。production fallback はその理由をログにせず、次の kernel に進む。`src/prefill/kernels.cu:1374-1397, 3192-3194`。

Strata の `docs/DETAILS.md:1082, 1530` および `docs/AMD_HIP.md:304-321` は CUDA と gfx11 HIP の適用範囲を記載しているが、この commit のソースには gfx12 の自動経路と Linux 全 gfx12 向け既定値注入もある。資料の性能値は本書では現行条件の測定値として採用しない。

## 根拠

- 候補変数の既定値と上書き規則: `src/core/arch_defaults.cpp:218-223, 278-290`; 適用条件と呼び出し時点: `src/program/generate.cpp:4074-4107`。
- CUDA parse、SM bypass、eligibility、scratch/fallback: `src/prefill/kernels.cu:1230-1281, 1251-1255, 1374-1397, 3110-3194`。
- HIP parse、自動閾値、gfx11/gfx12 eligibility と fused path: `src/prefill/kernels.cu:1826-1843, 2137-2172, 2177-2214, 3011-3025, 3223-3231`。
- 現行文書との照合: `docs/DETAILS.md:1082, 1530`; `docs/AMD_HIP.md:304-321`。
