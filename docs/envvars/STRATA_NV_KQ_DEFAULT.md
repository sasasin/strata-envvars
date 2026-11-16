# `STRATA_NV_KQ_DEFAULT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

CUDA の `strata generate` 起動時に、K-quant expert の prompt 計算で使う `STRATA_MMQ_KQ=1` を Strata が既定設定するかを制御する。既定では compute capability major 8 以上でこの既定値を設定する。`STRATA_NV_KQ_DEFAULT` 自体はカーネル選択に渡されず、`nv_kq_default_env()` が既定値を返すかどうかだけを決める（`src/core/nv_defaults.cpp:126-139`、`src/program/generate.cpp:4225-4241`）。

この変数は `STRATA_MMQ_KQ` を強制的に ON/OFF する設定ではない。既定値の候補があるときも、`STRATA_MMQ_KQ` がすでに設定されていれば空文字を含めて上書きしない。実際の MMQ K-quant 経路は `STRATA_MMQ_KQ` を別途判定する（`src/core/nv_defaults.cpp:178-191`、`src/prefill/moe_mmq.cu:43-55`）。

## 値と判定

`std::getenv` で値を取得し、値が存在して先頭文字が `'0'` の場合だけ既定値の追加を止める。数値変換や文字列全体の比較はせず、大文字小文字・空白・後続文字も検査しない。`kNvKqDefaultOn` は `true` なので、先頭が `'1'` の値に特別な効果はなく、その他の値は未設定と同じく既定値を許可する（`src/core/nv_defaults.cpp:130-139`、`include/strata/core/nv_defaults.hpp:39-47`）。

| 条件 | unset | 既定値を許可する例 | 既定値を止める例 |
|---|---|---|---|
| `STRATA_DEFAULTS=026` ではなく、可視 CUDA GPU の最低 compute capability major が 8 以上 | `STRATA_MMQ_KQ=1` の既定値を候補にする | 空文字、`1`、`true`、` 0`、`0anything` 以外で先頭が `0` でない値 | `0`、`0anything` |
| `STRATA_DEFAULTS=026`、または最低 major が 8 未満 | GPU 条件または旧既定値モードにより候補なし | 対象変数の値にかかわらず候補なし | 対象変数の値にかかわらず候補なし |

空文字は設定済みだが先頭文字は NUL なので、既定値を止めない。`0anything` は先頭が `0` のため止める。`STRATA_DEFAULTS` が `026`、`0.2.6`、`v0.2.6` のいずれかなら旧既定値モードになり、この候補自体を作らない。`STRATA_DEFAULTS` は初回参照時に関数内 `static` へ保存される（`src/core/nv_defaults.cpp:132-139`、`include/strata/core/defaults_026.hpp:21-29`）。

## 有効になる条件

- CUDA の `strata generate` 経路で GPU 情報が取得でき、可視 GPU が 1 台以上あること。全 GPU の compute capability が同一であることは別の `STRATA_SM86_PERF` 等の既定値に関係するが、K-quant 既定値の判定は可視 GPU の最低 compute capability を使う（`src/program/generate.cpp:4214-4241`）。
- 最低 compute capability major が 8 以上で、`STRATA_DEFAULTS` が旧既定値トークンでなく、対象変数の先頭文字が `0` でないこと（`src/core/nv_defaults.cpp:130-139`）。
- `STRATA_MMQ_KQ` が未設定であること。設定済みなら `apply_nv_kq_default()` はその値を保つ。後段の MMQ判定では先頭文字が `1` の値だけが ON になるため、既存値 `0`、空文字、`true` などは既定追加を妨げたうえで K-quant MMQ を有効にしない（`src/core/nv_defaults.cpp:178-187`、`src/prefill/moe_mmq.cu:46-55`）。
- 実際の計算経路には、K-quant の対象型を持つ native expert model と、その型を扱うビルドが必要。Strata が対象とする型は Q4_K、Q5_K、Q6_K、Q5_1。モデルがこれらを含まなければ起動時の K-quant 案内も出ない（`include/strata/core/nv_defaults.hpp:53-58`、`src/program/generate.cpp:5064-5070`）。
- CUDA MMQ ビルドでは `STRATA_MMQ_KQUANTS` のコンパイルと MMQ 経路が必要。CUDA で `STRATA_MMQ=OFF` のビルドは Strata 自身の prompt kernels を使う構成であり、この変数による MMQ 既定値設定だけで MMQ kernels がビルドされることはない（`CMakeLists.txt:106-112,611-615`）。K-quant MMQ を含む場合も、融合 kernel が対象層を処理すればその層では `STRATA_PF_FUSED_KQ` など別の条件が使われる（`src/core/nv_defaults.cpp:142-147,160-164`）。
- `--serve` に専用の優先規則はない。環境の既定追加はモデルの expert layout を調べる前の起動処理であり、実際に対象形式の expert があるかを見て案内行を出す（`src/program/generate.cpp:4208-4241,5035-5070`）。

## 実行時の詳細

CUDA GPU の初期化後、`generate.cpp` は可視 GPU の最低 compute capability を求めて `apply_nv_kq_default()` を呼ぶ。判定を通ると、`STRATA_MMQ_KQ` が未設定の場合にだけ値 `1` をプロセス環境へ設定する（Windows は `_putenv_s`、それ以外は `setenv(..., 0)`）。この処理はモデルの expert layout を読み込む前に一度行われる。対象変数は呼び出し時に通常の `getenv` で評価し、関数内キャッシュはない。一方 `STRATA_DEFAULTS` は初回参照時の値を cache する。子プロセスへの環境転送を行うコードはこの経路にはない（`src/core/nv_defaults.cpp:126-139,178-191`、`src/program/generate.cpp:4208-4241,5035-5043`）。

`STRATA_NV_KQ_DEFAULT=0` は新たな `STRATA_MMQ_KQ=1` の注入を止めるだけで、すでに設定された `STRATA_MMQ_KQ=1` を消去しない。逆に対象変数が許可しても、`STRATA_MMQ_KQ` がすでに `0` または空文字なら上書きされず、MMQ の K-quant 判定は OFF になる。通常の MMQ 実装では `STRATA_MMQ_KQ` の先頭文字が `1` かを初回判定で cache し、DSO 構成では loader の `wanted()` が同様に cache する（`src/prefill/moe_mmq.cu:46-55`、`src/prefill/mmq_kq_loader.cpp:108-116`）。

MMQ K-quant がビルドされている CUDA 構成では、対象型の積を MMQ 経路へ振り分ける。DSO 構成では K-quant library を engine と同じディレクトリから開き、ABI と全 GPU の初期化を確認してから使う。ライブラリがない、別バージョン、GPU 初期化失敗の場合は Strata が stderr に理由を出し、その expert は FP16 prompt path に戻る。カーネル呼び出し自体が非ゼロのエラーを返すと `prefill mmq: the K-quant library failed on type ...` を出して `exit(1)` する（`src/prefill/mmq_kq_loader.cpp:58-98`、`src/prefill/moe_mmq.cu:420-428`）。

## ログと測定値

この環境変数自体の値や既定値追加だけを知らせるログはない。対象型を持つ native expert model で既定値候補がある場合、expert layout 読み込み後に `strata: a model with K-quant experts ...` の行を stderr に出す。候補があれば `STRATA_MMQ_KQ` がすでに設定済みでも `apply_nv_kq_default()` はその名前を返すため、明示値 `STRATA_MMQ_KQ=0` の場合にも案内行は出る一方、MMQ K-quant の実際の判定は OFF のままである。MMQ build で融合 kernel が対象を担当する場合と、MMQ のない build では案内文が異なる。対象型のないモデル、CUDA GPU を列挙できない場合、`STRATA_DEFAULTS=026`、またはこの変数で既定値候補が止まる場合は、この既定処理から案内行を出さない（`src/program/generate.cpp:4210-4241,5064-5070`、`src/core/nv_defaults.cpp:149-165,178-190`）。

DSO が見つからない場合は `strata: K-quant prompt kernels (STRATA_MMQ_KQ=1): %s not found next to the engine - these experts take the FP16 prompt path`、ABI 不一致の場合は `strata: K-quant prompt kernels: %s is from another engine version - these experts take the FP16 prompt path`、GPU 初期化失敗の場合は `strata: K-quant prompt kernels: %s did not start on GPU %d (CUDA error %d) - these experts take the FP16 prompt path` を stderr に出す。成功時は `strata: K-quant prompt kernels from %s (STRATA_MMQ_KQ=1)` を出す（`src/prefill/mmq_kq_loader.cpp:66-97`）。

`docs/DETAILS.md` は gfx12/Linux と `STRATA_MMQ_KQ` による切替を説明しているが、ここで調べた環境変数の CUDA 既定値ゲートは説明していない。同資料の速度・KL 値は gfx12 の `STRATA_MMQ_KQ` 経路についての記載であり、この変数固有の測定値としては扱わない（`docs/DETAILS.md:1058`）。

## 根拠

- 候補変数の読み取り、GPU 条件、既定値: `src/core/nv_defaults.cpp:126-139`
- 既定値の注入と既存値の保持: `src/core/nv_defaults.cpp:178-191`
- GPU 判定と起動時の呼び出し: `src/program/generate.cpp:4208-4241`
- expert layout による案内行の条件: `src/program/generate.cpp:5064-5070`; `include/strata/core/nv_defaults.hpp:53-58`
- `STRATA_MMQ_KQ` の読み取りと型 dispatch: `src/prefill/moe_mmq.cu:43-55,420-428`
- CUDA K-quant loader とログ・fallback: `src/prefill/mmq_kq_loader.cpp:58-116`
- backend/build 条件: `CMakeLists.txt:106-112,611-615`
- `STRATA_DEFAULTS` の値判定と cache: `include/strata/core/defaults_026.hpp:21-29`
- 既存設計資料: `docs/DETAILS.md:1058`
