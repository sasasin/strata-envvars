# `HY4S_NO_XMX`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の SYCL 実装で、選択中の SYCL デバイスを XMX 対応として扱う判定を抑止する。値が条件に合うと `DevCaps::has_xmx_sg8` と `has_xmx_sg16` が初期値の `false` のままになり、これらのフラグで選ぶ XMX カーネルが使われず、各呼び出し側の SIMT 等の経路へ進む（`engine/src/hy4flash/sycl/sy_common.h:181-195,198-258`）。この環境変数は `engine/src/hy4flash/sycl/sy_common.h` の `dev_caps()` にある直接の `std::getenv` で読み取られる。候補名は索引にも掲載されている（`docs/envvars/000_envvers.md:415`）。

これは SYCL 用の能力判定を変える設定で、GPU の subgroup 能力 (`has_sg8` / `has_sg16`)、グラフ能力、GPU 選択自体はこの変数では変更しない。通常の実行経路がこの能力フラグを使う箇所には、量子化 GEMM、expert GEMM、vision GEMM、indexer scoring、MLA の prefill 処理がある（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:910-940`、`engine/src/hy4flash/sycl/sy_gpuexp.cpp:509-518`、`engine/src/hy4flash/sycl/sy_vision.h:97-101,174-183`、`engine/src/hy4flash/sycl/sy_indexer.h:352-368`、`engine/src/hy4flash/sycl/sy_mla.cpp:1717-1734,1758-1775,1794-1828`）。

## 値と判定

`dev_caps()` の初回評価時に `std::getenv("HY4S_NO_XMX")` が非 null で、かつその値の先頭文字が `'1'` の場合だけ `no_xmx` が true になる。文字列全体の比較や数値変換はしない。したがって unset と空文字は false、`1`、`10`、`1anything` は true、`0`、`true`、` 1`、`01` は false である。大文字小文字や後続文字は判定されず、空白の trim もない（`engine/src/hy4flash/sycl/sy_common.h:221-222`）。

| ビルド・実行条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `engine/src/hy4flash/sycl` の SYCL 実装 | デバイス名・architecture・PCI ID の認識と subgroup size に応じて XMX 能力を判定 | 先頭が `1` の値（例: `1`, `1anything`）で SG8 / SG16 XMX 能力を無効扱いにする | 空文字、`0`, `true`, ` 1`, `01` は抑止しない。通常のデバイス能力判定へ進む |

通常の能力判定では、デバイス名、（ビルド時に利用可能なら）SYCL architecture、特定 PCI ID のいずれかで Arc/XMX 系と認識され、SG8 があれば SG8、そうでなく SG16 があれば SG16 の XMX フラグを立てる。`HY4S_NO_XMX` が有効な場合はこの認識処理全体を飛ばす（`engine/src/hy4flash/sycl/sy_common.h:218-255`）。

## 有効になる条件

- 環境変数を読むのは Hy4-Flash SYCL 実装の `dev_caps()` である。CUDA/HIP その他の実装について、この変数を読む箇所はソース全体の名前検索では見つからなかった（直接参照は `engine/src/hy4flash/sycl/sy_common.h:221` のみ）。
- 実際のカーネル選択に影響するのは、呼び出し側が `has_xmx_sg8` / `has_xmx_sg16` を確認する経路である。SG8 をビルドから除く `HY4S_DISABLE_SG8`、SG16 経路を含める `HY4S_ENABLE_SG16_XMX` により利用可能な枝は異なる。`build_hy4_sycl.sh bmg` は SG8 を無効にし SG16 を有効にする。`fat` と `acm` はこのスクリプトでは SG16 を有効にしない（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:26-35`）。`HY4S_NO_XMX=1` なら、ビルドに含まれている SG8/SG16 のいずれの能力フラグも立たない。
- 量子化 GEMM の `dispatch_xmx_fmt` は有効な SG8/SG16 枝がなければ `k_gemm_simt_sg32` に進む。expert GEMM も XMX 枝が使えない場合は `launch_gemm_simt` を呼ぶ（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:910-940`、`engine/src/hy4flash/sycl/sy_gpuexp.cpp:509-518`）。vision GEMM は SG8 XMX の枝を抜け、SG32 tiled GEMM に進む（`engine/src/hy4flash/sycl/sy_vision.h:97-101,174-183`）。indexer の通常 scoring は XMX 枝を使う条件に `T >= 16` も含み、条件を満たさない場合は SG32 の scoring に進む（`engine/src/hy4flash/sycl/sy_indexer.h:352-368`）。
- MLA の通常関数では prefill `M >= 16` が XMX 経路の条件であり、attention はさらに `TK == 64` かつ `a.tree.n == 0` を要する。能力フラグが false なら `prep_q_t` / `vup_t` / `attend_t` 側へ進む。`HY4S_MLA_XMX` が先頭 `0` の場合も独立に MLA の XMX を抑止するが、`HY4S_NO_XMX` が有効なときに同変数で XMX 能力を再有効化する経路はない（`engine/src/hy4flash/sycl/sy_mla.cpp:29-42,1717-1734,1758-1775,1794-1828`）。
- `HY4S_USE_ONEMKL` を付けたビルドの `linear_auto` は、対応する形式・行列寸法などの条件を満たすと `gemm_onemkl` を `dev_caps()` による dispatch より先に試す。そこに `HY4S_NO_XMX` の確認はないため、この変数が同経路を止めるとは言えない。oneMKL 経路が使えない場合の `dispatch_xmx_fmt` は能力フラグで選択される（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:856-865,889-940,967-985`）。
- `HY4S_CPU_DEVICE` の先頭が `1` ならキューは SYCL CPU device を選ぶ。これは GPU 選択条件であり、`HY4S_NO_XMX` は選択デバイスの能力判定後に XMX フラグへ作用する（`engine/src/hy4flash/sycl/sy_common.h:154-175,198-221`）。

## 実行時の詳細

`dev_caps()` は関数内 `static DevCaps c` を初回呼び出し時に構築し、その初期化ラムダの中で環境変数を読む。一度 `dev_caps()` が初期化された後にプロセス環境を変えても、この能力値は再評価されない。読み取りを子プロセスへ転送・上書きする処理は、この変数の参照箇所にはない（`engine/src/hy4flash/sycl/sy_common.h:198-221,257-259`）。

CLI 引数による直接の上書きはない。通常 CLI はモデル名を確認した後に `dev_caps()` を呼び、能力情報を stderr に出す。`--serve` は `hy4s_serve_main()` へ先に分岐するため、この通常 CLI の `[gpu]` 行は通らない（`engine/src/hy4flash/sycl/sy_main.cpp:215-259`）。ただし server 起動も後続の SYCL 処理で同じ `dev_caps()` の能力値を参照する。モデル状態によって XMX 実行が可能かは、各経路の M/TK/tree 等の条件にも依存する（上記「有効になる条件」参照）。

この変数自体による警告、エラー、終了処理は実装されていない。先頭が `1` の値で通常 CLI を実行した場合に観測できるのは、GPU 情報行の `xmx8=0 xmx16=0` である（`engine/src/hy4flash/sycl/sy_main.cpp:255-259`）。この値は能力フラグを示し、`HY4S_USE_ONEMKL` 経路の利用可否を表すものではない。

ソース上の効果はカーネル経路の選択変更までで、生成 token や数値結果が同一であること、性能差、失敗率はこの commit のソースだけからは確認できない。`docs/` にこの環境変数固有の測定値や説明は見つからなかった。

## 根拠

- 直接の読み取り、値判定、デバイス能力のキャッシュと設定: `engine/src/hy4flash/sycl/sy_common.h:181-259`
- 能力フラグを使う GEMM / expert / vision / indexer / MLA の分岐: `engine/src/hy4flash/sycl/sy_gemm_xmx.h:910-985`、`engine/src/hy4flash/sycl/sy_gpuexp.cpp:509-518`、`engine/src/hy4flash/sycl/sy_vision.h:97-101,174-183`、`engine/src/hy4flash/sycl/sy_indexer.h:352-394`、`engine/src/hy4flash/sycl/sy_mla.cpp:29-42,1717-1830`
- build macro と実行モードによる差: `engine/src/hy4flash/sycl/build_hy4_sycl.sh:26-49`、`engine/src/hy4flash/sycl/sy_main.cpp:199-259`
