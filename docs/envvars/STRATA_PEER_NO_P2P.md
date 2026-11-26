# `STRATA_PEER_NO_P2P`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は CUDA の `--peer-device` expert tier が二 GPU 間の直接 P2P 経路を使うかどうかに介入する開発・診断用 knob です。`atoi(value) != 0` なら P2P を使えないものとして扱い、expert 計算の入出力を pinned host staging 経由にします。`atoi(value) == 0` で空でない値なら、Linux PCIe topology による P2P の事前拒否を解除します。ただし、後段の実コピー検査に失敗すれば P2P は無効になります。実装は `PeerExperts::open` と `p2p_topology_safe` です（`engine/src/core/peer_experts.cpp:62-103,192-235`）。

同じ変数は CUDA native output head の GPU 分割にも関与し、数値として非ゼロなら `STRATA_PEER_HEAD_SPLIT` による分割を抑止します（`engine/src/core/native_head.cpp:131-140`）。

## 値と判定

いずれの箇所も文字列全体の検証ではなく `std::atoi` を使います。先頭の空白と符号を含む整数接頭辞が変換され、数字以降の文字列は検査されません。数値に変換できない文字列は 0 になります。大文字小文字の概念はありません。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `--peer-device` の `PeerExperts::open` | P2P を禁止しない | `1`, `-1`, `1tail`（`atoi != 0` で P2P 候補を強制的に無効化） | `0`, `0tail`, `true`, 空文字（`atoi == 0` なので禁止しない） |
| P2P 候補に対する topology 判定 | 通常の topology 判定 | `0`, `0tail`, `true`, 空文字以外で `atoi == 0` となる非空値（topology による拒否を迂回） | `1`, `-1`, `1tail`, 空文字（topology 拒否を迂回しない） |
| CUDA native head 分割 | この変数では分割を抑止しない | `1`, `-1`, `1tail`（非ゼロなので分割条件を不成立にする） | `0`, `0tail`, `true`, 空文字（`atoi == 0` なので抑止しない） |

topology 判定だけは `np != nullptr && np[0] != '\0' && atoi(np) == 0` を条件とします。そのため空文字は `atoi` 自体は 0 でも topology override にはならず、空でない `true` や `0tail` は override になります。`PeerExperts::open` と native head の分岐は空文字を特別扱いせず、`atoi("") == 0` として扱います（`engine/src/core/peer_experts.cpp:63,212`; `engine/src/core/native_head.cpp:133-136`）。範囲制限、無効文字列のエラー、fallback 値の parse はありません。

## 有効になる条件

- P2P の禁止・topology override は `PeerExperts::open` が実行される `strata generate --peer-device N` 経路で評価されます。peer device には expert profile と有効な expert cache が必要で、初期化失敗時は generate がエラーを stderr に出して終了コード 1 で戻ります（`engine/src/program/generate.cpp:10211-10227`）。
- direct P2P を使うには両方向の `cudaDeviceCanAccessPeer` が真である必要があります。非ゼロ値はこのうち一方向の結果を 0 にして P2P を無効にします（`engine/src/core/peer_experts.cpp:208-214`）。
- 数値 0 の topology override は topology 安全性検査のみを迂回します。P2P 有効化と両方向のテストコピーは引き続き実行され、P2P 設定が失敗するか、コピー内容が一致しない／検査時間が閾値を超える場合はホスト経由に戻ります（`engine/src/core/peer_experts.cpp:105-148,219-235`）。
- P2P が無効の場合、prefill の host route は既定で許可されます。`STRATA_PF_PEER_HOST=0` なら `prefill peer: the two GPUs cannot access each other (no P2P)` で失敗する経路があります（`engine/src/prefill/prefill.cpp:3333-3340`）。
- native head 分割側は `__HIPCC__` と `STRATA_GPU_METAL` の build ではコンパイル対象外です。さらに `STRATA_PEER_HEAD_SPLIT` が非ゼロ、異なる有効な peer device がある、`STRATA_HEAD_HOST` が未設定、native Q6_K packed が無効、Q8_0 head の場合は `STRATA_Q8_SM60` が未設定、出力行数が 2 以上、かつ本変数が数値として非ゼロでないことが必要です。二方向の P2P access も必要です（`engine/src/core/native_head.cpp:130-140`）。

## 実行時の詳細

`PeerExperts::open` は peer tier の初期化時に値を読み、P2P 候補と topology 判定を決めます。値は関数内 static に保存されず、別の `p2p_topology_safe` 呼び出しでも `getenv` し直します。通常のプロセス内でこの初期化後に環境を変更しても、既に決まった `p2p_` は再評価されません。コードに CLI 引数・設定ファイルによる本変数の上書きはありません（`engine/src/core/peer_experts.cpp:62-63,192-235`）。

`atoi(value) != 0` で P2P が無効になった場合、peer expert の入力と結果は pinned host staging バッファを経由し、peer GPU の結果行は host 側へコピーされます。P2P が有効で、`STRATA_PEER_DIRECT` も有効、かつ出力先がある場合は結果を直接出力先へ scatter する経路が選ばれます（`engine/src/core/peer_experts.cpp:315-322,363-394`; `engine/src/core/expert_source.cpp:5681-5715`）。

native head では `NativeHead::load` 時に `STRATA_PEER_HEAD_SPLIT` と本変数を読みます。本変数が非ゼロなら分割条件を満たさず、通常の single-GPU output head 読み込みへ進みます。プロセス起動後に値を変更しても、読み込み済み head や開始済み peer tier には反映されません（`engine/src/core/native_head.cpp:98-140,218-255`; 呼び出し元 `engine/src/program/generate.cpp:8391-8395`）。

## ログと測定値

- Linux の topology 検査で unsafe と判定され、override がない場合、stderr に `strata: peer GPU %d: GPUs sit behind a PCIe host bridge (PHB/SYS, no shared PCIe switch or NVLink); using portable host-pinned staging instead of P2P (STRATA_PEER_NO_P2P=0 overrides)` を出します（`engine/src/core/peer_experts.cpp:214-217`）。
- P2P を有効化した後の検査コピーで不一致等が見つかった場合、stderr に `strata: peer GPU %d: peer access is enabled but a test copy between the two GPUs arrived wrong (a host bridge between them, no real P2P): the prompt path takes the host route instead (STRATA_PEER_NO_P2P=1 does that by hand)` を出し、両方向の peer access を無効化します（`engine/src/core/peer_experts.cpp:227-235`）。
- host route に切り替わったこと自体を別途必ず表示するログは、これらの条件付き理由ログ以外には確認できません。native head 分割時には `strata generate: STRATA_PEER_HEAD_SPLIT=1: split output head ... over P2P`、分割中の allocation 失敗時には `strata generate: STRATA_PEER_HEAD_SPLIT=1 fell back to single-GPU output head (P2P allocation failed)` を stderr に出します（`engine/src/core/native_head.cpp:202-212`）。
- `docs/SECOND_GPU.md:84-86` は `STRATA_PEER_NO_P2P=1` による host route を記載していますが、現行コードでは `0` が topology の事前拒否を override する条件もあります。これは安全性検査の迂回であり、最終的に P2P が使われる保証ではありません。
- この調査では build・GPU 実行・性能測定を行っていません。コードコメント中の過去のコピー時間例を本変数の測定結果として扱っていません。

## 根拠

- `engine/src/core/peer_experts.cpp:62-103` — topology safety 判定と環境値による override。
- `engine/src/core/peer_experts.cpp:105-148` — 双方向の test copy と判定条件。
- `engine/src/core/peer_experts.cpp:192-235` — peer 初期化、P2P 強制無効化、ログと fallback。
- `engine/src/core/peer_experts.cpp:315-394` — direct mode と host staging の計算経路。
- `engine/src/core/native_head.cpp:98-140,202-212` — native head の分割条件とログ。
- `engine/src/core/expert_source.cpp:5681-5715` — peer 計算結果の direct / host 出力選択と launch failure。
- `engine/src/prefill/prefill.cpp:3333-3385` — P2P 不在時の prefill host route 条件。
- `engine/src/program/generate.cpp:10211-10227` — `--peer-device` の起動条件と初期化失敗時の終了。
