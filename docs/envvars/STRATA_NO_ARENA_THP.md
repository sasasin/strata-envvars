# `STRATA_NO_ARENA_THP`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Linux の expert arena を確保したときに、Strata がその領域へ `madvise(..., MADV_HUGEPAGE)` を要求するかを選びます。`STRATA_NO_ARENA_THP` は arena の huge-page backing を禁止する設定ではなく、Strata からの THP 要求を省く設定です。未設定時には integrated gfx11 GPU 向けの既定ルールがあり、明示値 `0` はそのルールを上書きして要求を試みます。CUDA/HIP 共通の `src/core/pinned.cu` と SYCL の `sycl/src/core/pinned.dp.cpp` が読み取ります（`src/core/pinned.cu:462-496`, `sycl/src/core/pinned.dp.cpp:229-260`）。

Windows 側の arena 確保は `VirtualAlloc` 分岐で、この変数を読みません。Linux では、通常の大ページ確保を試した後に 2 MiB 境界の匿名 arena を作る経路で判定します。したがって、先に `MAP_HUGETLB` 等による大ページ確保に成功して返る場合、この変数による THP 判定は行われません（`src/core/pinned.cu:437-447`, `src/core/pinned.cu:462-496`; SYCL 対応箇所は `sycl/src/core/pinned.dp.cpp:203-214`, `sycl/src/core/pinned.dp.cpp:229-260`）。

## 値と判定

両 backend とも `std::getenv` の結果を文字列全体として parse せず、設定の有無と先頭 1 文字だけで判定します。`"0"` で始まる値は THP 要求を許可し、それ以外の設定値は要求を省きます。数値変換、空白除去、大文字小文字変換はありません（`src/core/pinned.cu:494-496`, `include/strata/core/arch_defaults.hpp:90-92`; SYCL は `sycl/src/core/pinned.dp.cpp:258-260`）。

| 条件 | unset | 要求を試みる値（例） | 要求を省く値（例） |
|---|---|---|---|
| Linux CUDA/HIP、THP が `always` ではない | integrated gfx11 の既定ルールに従う。それ以外は要求する | `0`, `00`, `0anything`, `0 ` | 空文字、`1`, `true`, `false`, `anything`, ` 0` |
| Linux SYCL、THP が `always` ではない | 要求する | `0`, `00`, `0anything`, `0 ` | 空文字、`1`, `true`, `false`, `anything`, ` 0` |
| Linux CUDA/HIP / SYCL、THP が `always` | 要求しない | なし（`0` でも要求しない） | unset を含むすべて |
| Windows | この変数を読まず、THP 要求経路もない | 該当なし | 該当なし |

「要求する値」は実際に `madvise` が成功する意味ではありません。THP が `always` の場合は設定値 `0` よりも「追加要求をしない」判定が優先されます。また CUDA/HIP の Linux 経路では、他の条件により `madvise` 自体が呼ばれない場合があります（`src/core/pinned.cu:481-496`, `src/core/pinned.cu:506-519`; `sycl/src/core/pinned.dp.cpp:247-260`, `sycl/src/core/pinned.dp.cpp:261-268`）。

## 有効になる条件

- Windows 以外の CUDA/HIP または SYCL 実装で、expert arena が通常ページの匿名 mapping として確保され、THP 判定箇所に到達する必要があります。Windows 分岐には読み取りがありません（`src/core/pinned.cu:151-152`, `src/core/pinned.cu:462-496`; `sycl/src/core/pinned.dp.cpp:64-65`, `sycl/src/core/pinned.dp.cpp:229-260`）。
- unset の場合、CUDA/HIP engine は Linux 上の integrated `gfx1103` / `gfx1150` / `gfx1151` で要求を省きます。判定は device が integrated で、Windows ではなく、architecture 名が上記のいずれかであることに基づきます。それ以外は要求を試みます（`src/program/generate.cpp:4107-4120`, `src/core/arch_defaults.cpp:151-155`, `include/strata/core/arch_defaults.hpp:90-92`）。
- SYCL は同じ `STRATA_NO_ARENA_THP` の文字列規則と THP `always` 判定を使いますが、`arena_no_thp_flag()` による GPU 別既定ルールは参照しません。unset かつ THP が `always` でない場合、SYCL は要求を試みます（`sycl/src/core/pinned.dp.cpp:257-268`）。
- Linux の `/sys/kernel/mm/transparent_hugepage/enabled` から選択中の mode を読み取れない場合、`thp_mode` は空のままなので、Strata の `always` 判定には該当しません（`src/core/pinned.cu:480-488`, `sycl/src/core/pinned.dp.cpp:247-255`）。
- `STRATA_NO_LARGEPAGES` が設定されていると、CUDA/HIP と SYCL の通常 mapping 経路は THP 判定後のログ更新・`madvise` 呼び出しを抑止します。このとき本変数の値だけでは THP 要求は発生しません。同変数は先行する hugetlb 大ページの試行も抑止します（`src/core/pinned.cu:437-460`, `src/core/pinned.cu:497-519`; `sycl/src/core/pinned.dp.cpp:203-227`, `sycl/src/core/pinned.dp.cpp:261-268`）。
- CUDA/HIP では、`STRATA_ARENA_THP` が設定されていない場合、空き 2 MiB block が arena サイズの半分未満なら `MADV_HUGEPAGE` を要求せず、理由をログに出します。`STRATA_ARENA_THP` は値でなく `getenv(...) != nullptr` で存在判定されるため、空文字でもこの抑止条件を解除します。SYCL にはこの free-block 判定がありません（`src/core/pinned.cu:506-519`, `sycl/src/core/pinned.dp.cpp:261-273`）。この条件で抑止されたときも、対象変数がその理由を指示したのではなく、free-block 判定が優先されています。
- `STRATA_NO_ARENA_THP` 用の CLI 引数はありません。直接 engine を起動する場合はプロセス環境が読み取られます。server は親環境のコピーに run config の `env` を後から適用するため、同名設定が両方にある場合は config 値が engine に渡されます（`serve/server.py:4428-4441`）。Setup は gfx1103 opt-in かつ Linux HIP の run config に `STRATA_NO_ARENA_THP=1` を追加します（`strata_control/setup_config.py:443-449`）。

## 実行時の詳細

値は arena の通常 mapping を用意するたびに `reserve()` 内で `getenv` され、関数 static などへの cache はありません。プロセス起動後に外部から環境を書き換えても、すでに確保済みの arena の判定結果は変わりません。設定は arena 作成時に読み取られ、その後の model load / engine 処理で再評価される経路はありません（`src/core/pinned.cu:146-147`, `src/core/pinned.cu:467-496`, `include/strata/core/pinned.hpp:43-45`; `sycl/src/core/pinned.dp.cpp:60-61`, `sycl/src/core/pinned.dp.cpp:234-260`）。

unset の CUDA/HIP 既定ルールを立てる呼び出し元は、engine が GPU architecture と integrated 判定を得た後に `arena_no_thp_flag` を設定します。対象は integrated gfx11 の Linux GPU（gfx1103、gfx1150、gfx1151）です。明示値 `"0"` はこの flag による抑止を上書きします。一方、他の設定値は device 既定にかかわらず要求を省きます（`src/program/generate.cpp:4107-4120`, `src/core/arch_defaults.cpp:151-155`, `include/strata/core/arch_defaults.hpp:90-92`）。

要求を省く分岐では Strata が `madvise` を呼ばず、arena note に理由を付けます。要求分岐では `madvise(p, bytes, MADV_HUGEPAGE)` を呼び、戻り値が 0 の場合だけ note に `; transparent huge pages requested (MADV_HUGEPAGE)` を加えます。呼び出し失敗時の専用エラーや警告はこの箇所にはなく、要求成否の外部結果は記録しません。`STRATA_NO_LARGEPAGES` が未設定なら、engine の起動ログには `strata generate: expert arena: ...` として note が出ます（`src/core/pinned.cu:497-524`, `src/program/generate.cpp:8355-8360`; SYCL note は `sycl/src/core/pinned.dp.cpp:261-274`）。

## ログと測定値

読み取り値そのものを出力するログはありません。一般的な値で THP 要求を省いた場合、arena note に `; transparent huge pages skipped (STRATA_NO_ARENA_THP)` が入り、engine は `strata generate: expert arena: ...` と出力します。unset の gfx11 既定ルールで省いた場合は `; huge pages not requested on this graphics chip`、THP mode が `always` の場合は `; transparent huge pages are on for every mapping (THP always): MADV_HUGEPAGE not requested` です（`src/core/pinned.cu:501-505`, `src/program/generate.cpp:8355-8358`; SYCL の対応文言は `sycl/src/core/pinned.dp.cpp:265-267`）。

CUDA/HIP で free-block 判定が要求を止める場合は、`strata: expert arena: ...` の行をその場で stderr に出します。要求成功時の note は後続の `strata generate: expert arena: ...` に現れます。`madvise` が失敗すると成功文言は付かず、専用の失敗ログもありません（`src/core/pinned.cu:506-524`, `src/program/generate.cpp:8355-8358`）。

`docs/DETAILS.md` にこの環境変数についての追加説明や測定値はありません。`docs/TROUBLESHOOTING.md:119-121` は、THP mode `always` のとき追加要求をしない理由と、`STRATA_NO_ARENA_THP=1` が任意の mode で要求を省くことを説明しています。現在の実装では、値 `0` の扱い、gfx11 の unset 既定、SYCL 差分、および他の環境変数との条件も上記のとおりです。

## 根拠

- 値判定と THP mode 判定: `src/core/pinned.cu:480-496`, `include/strata/core/arch_defaults.hpp:86-92`, `sycl/src/core/pinned.dp.cpp:247-260`
- device 既定の範囲と設定箇所: `src/core/arch_defaults.cpp:151-155`, `src/program/generate.cpp:4107-4120`
- free-block 判定、相互作用、ログ文言: `src/core/pinned.cu:497-524`, `sycl/src/core/pinned.dp.cpp:261-274`, `src/program/generate.cpp:8355-8360`
- setup と server の環境引き渡し: `strata_control/setup_config.py:443-449`, `serve/server.py:4428-4441`
- 既存の Strata 説明: `docs/TROUBLESHOOTING.md:119-121`
