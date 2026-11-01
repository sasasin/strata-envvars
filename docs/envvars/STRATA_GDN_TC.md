# `STRATA_GDN_TC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA の GDN（DeltaNet）prefill recurrence で、通常の FP32 recurrence kernel の代わりに tensor-core を使う chunked scan を選ぶ opt-in switch です。Strata がこの変数を読むのは `src/prefill/kernels.cu` の CUDA dispatch です。HIP 用の同ファイルの分岐は別の kernel を選び、この変数を読みません。

この dispatch は通常の `gdn_recurrence()` と state-only の `gdn_recurrence_state_only()` で共有されています。実際のモデル prefill は GDN 層でこの関数を呼びます。したがって、値が有効でも GDN 層のないモデルや prefill recurrence を実行しない経路には効果がありません（`src/prefill/kernels.cu:2876-2880,3073-3085`; 呼び出し元 `src/prefill/prefill.cpp:3827-3831,6953-6956`）。

## 値と判定

値は `std::getenv` で取得し、`std::atoi(v) != 0` で判定します。文字列全体の厳密な数値検証はありません。

| 環境の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | `atoi("") == 0` となり無効 |
| 整数として先頭から 0 以外に変換される値（例 `1`, `-1`, `2`, `1junk`, ` 1`） | 有効 |
| 整数として変換できない値、または変換値が 0（例 `true`, `false`, `0`, `0tail`, `0.5`） | 無効 |

実装箇所は `src/prefill/kernels.cu:2982-2989` です。値に範囲制限や無効値警告はありません。

## 有効になる条件

環境変数が有効でも、次の条件を満たす場合だけ通常 dispatch が tensor-core 経路を試します。

- HIP ではない CUDA ビルドである（`src/prefill/kernels.cu:2982-2989,3062-3067`）。
- `with_out=true` の呼び出しで `STRATA_GDN_REC_HEADS` が設定されている場合は serial 経路に入るため、この dispatch を通らない。state-only 呼び出しは `with_out=false` なので serial 条件だけでは除外されない（`src/prefill/kernels.cu:2882,2977-2982`）。
- recurrence 呼び出しの `T >= 128`（`kGdnTcMin`; `src/prefill/kernels.cu:935,3027`）。
- CUDA device の compute capability major が 8 以上、SM 数が value head 数 `HV`（48）以上で、当該 scan に必要な opt-in shared memory を確保できる（通常 scan は `kTcScanSmem<false> == 124944` bytes）。scratch の確保も必要（`src/prefill/kernels.cu:1308-1327`; 定数 `src/prefill/gdn_tc.cuh:46-48`）。

通常 scan が要件を満たさない、または scratch allocation が失敗した場合、実装は split tensor-core scan を再試行します。split scan も要件（split 構成に応じ 97,808 または 98,832 bytes の shared memory）を満たさなければ、`STRATA_GDN_CHUNKED` が有効なら chunked FP32 scan、それも選ばれなければ `STRATA_GDN_PIPELINE` の既定 ON 判定と device eligibility に従って key-head / pipelined / columns kernel へ進みます（`src/prefill/kernels.cu:3027-3055`; shared-memory 値 `src/prefill/gdn_tc.cuh:52-55`）。したがって `STRATA_GDN_TC` は強制指定ではありません。

## 実行時の詳細

`tc` 判定は関数内 `static const bool` で、通常 dispatch が初めてこの箇所を通ったとき一度だけ評価されます。同一プロセスで後から環境を書き換えても再評価されません（`src/prefill/kernels.cu:2989`）。値の明示指定だけで別の CLI 引数より優先する機構はなく、Strata の通常 dispatch において `GdnProbe` が force path を指定する診断経路では `force != kGdnAuto` 分岐が優先され、環境変数による自動選択を通りません（`src/prefill/kernels.cu:2990-3004,3026-3029`）。

選択に成功すると `gdn_rec_tc()` が chunk ごとの prep と tensor-core scan kernel を stream に enqueue します。通常 scan の事前 eligibility / scratch check が error を返し、split scan の check が通れば split scan を使います。scan が `y16` を直接書かない経路では続けて output norm kernel を enqueue します（`src/prefill/kernels.cu:1348-1369,3068-3071`）。

適格性不足や scratch allocation 失敗は自動 fallback の理由になり、通常実行で `STRATA_GDN_TC` 専用の警告や選択ログは出しません。kernel launch のエラーは共通 `check("gdn_recurrence")` で stderr に `prefill gdn_recurrence: <CUDA error>` を出して `exit(1)` します（`src/prefill/kernels.cu:102-105,3071`）。診断用 `gdn_harness` は変数が設定されていれば値を `env STRATA_GDN_TC=<値>` として表示しますが、これは本番 engine のログではありません（`src/prefill/gdn_harness.cu:450-452`）。

Strata の server は `child_env()` で親環境を複製し、config の `env` を上書きした後、Linux の `qwen4exp` 用 GDN stack の CUDA pair に `setdefault` で値 `1` を入れます。従って親環境または config が `STRATA_GDN_TC` を明示していればその値を保ちます。既定設定は Linux 以外、arch が `qwen4exp` 以外、backend が SYCL/Metal/Vulkan のとき適用せず、HIP でもこの変数は設定せず、可視 GPU がすべて gfx12 なら別変数 `STRATA_GDN_CHUNKED=1` を設定します（`serve/server.py:3728-3745,3747-3764`）。この server 設定は子 engine の環境に渡されます。

## 既存資料との照合

`docs/GDN_CONTRACT.md:62-70` は production CUDA dispatch で `STRATA_GDN_TC=1` と `T >= 128` の場合に tensor-core scan を試し、sm_80 以上・48 SM 以上・共有メモリ条件が必要としています。これは現行コードの条件と一致します。`docs/DETAILS.md:1535-1545` はこの switch を CUDA prompt switch とし、CMP 170HX での測定値を変更作者の報告値として記載しています。そこにある性能値・数値誤差はこの調査で再測定していません。

## 根拠

- 読み取り、通常 dispatch、値の cache: `src/prefill/kernels.cu:2977-2999,3026-3055`
- tensor-core runtime eligibility、scratch、scan launch: `src/prefill/kernels.cu:1308-1369`
- minimum length と default fallback: `src/prefill/kernels.cu:935,2980-2989,3039-3071`
- HIP 分岐と CUDA の別 dispatch: `src/prefill/kernels.cu:2882-2892,2982-2989,3062-3067`
- production prefill 呼び出し: `src/prefill/prefill.cpp:3827-3831,6953-6956`
- server の既定値と子環境の構成: `serve/server.py:3728-3745,3747-3764`
- harness の診断表示: `src/prefill/gdn_harness.cu:450-452`
- 設計資料と報告測定: `docs/GDN_CONTRACT.md:62-70`; `docs/DETAILS.md:1535-1545`
