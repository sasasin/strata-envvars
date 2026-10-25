# `STRATA_PCIE_MIN1`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

decode の verify-window で expert pool が GPU 実行計画を作るとき、PCIe 経由で GPU に送る miss 数の share が整数丸めで 0 になった場合に、条件を満たせば少なくとも 1 miss を PCIe 側へ割り当てます。通常の share は `nmiss * pcie_num / 256` の整数部です。この変数は share が 1 以上ある場合の割り当て数を増やさず、CPU 計算対象のすべてを PCIe に移す設定でもありません。

## 値と判定

環境値は `std::atoi()` で整数に変換し、結果が 0 以外なら ON、0 なら OFF です。文字列全体の妥当性検査はありません。

| 値 | 判定 |
|---|---|
| unset | OFF |
| 空文字、数字で始まらない文字列、`0`、`0abc` | `atoi()` が 0 を返すため OFF |
| `1`、`-1`、`2` | 0 以外のため ON |
| `1abc`、` 1tail` | `atoi()` が先頭の整数部分を変換し 1 を返すため ON |

先頭の空白や符号は `atoi()` の規則で扱われ、整数部分の後ろにある文字列は判定に使われません。数値として 0 に変換された値は OFF です。値は `expert_pool_dispatch_multi()` 内の `static const bool` に保存され、該当コード経路で最初に初期化された後はプロセス内で再読込されません。プロセス起動後に環境を書き換えても反映されません。既定値は OFF です。

## 有効になる条件

変数が ON でも、次の条件を満たす verify-window の GPU 計画に限り、割当数の補正が行われます。

- `expert_pool_dispatch_multi()` の plan 作成経路に入り、plan sink が存在して容量条件を満たす。
- 対象 layer の `pcie_num` が正で、expert source の `pcie_layer(layer)` が true（`pcie_ok`）。従って `--pcie-frac` 相当の share が 0 の場合は補正されない。
- その layer の distinct miss 数 `nmiss` が 2 以上。
- 通常計算の割当 `m = (nmiss * pcie_num) >> 8` が 0。

これらを満たすと `m` を 1 にします。`m >= 1` なら値を変えても割当数は変わりません。選ばれるのは routing order 上の後ろ側の miss です。ただし実際に PCIe 扱いになるには、その expert の blob が pinned である必要があります。pinned でない場合はその expert の `kind` は miss のままとなり、CPU 側で処理されます。PCIe fetch の staging 枠数（`staging_cap` と最大 64 枠）に達した場合も、実際の PCIe fetch は行われません。

## 実行時の詳細

plan 作成時、コードはまず distinct routed expert のうち VRAM 常駐、peer/helper 保持分を除いて `nmiss` を数えます。`pcie_ok` と既定 share から `m` を計算し、環境変数が有効で `m < 1 && nmiss >= 2` の場合に 1 へ補正します。その後 routing order を走査し、後ろ側 `m` 件を PCIe 候補とします。候補が pinned なら blob pointer を取得し、GPU plan の PCIe group に加えて copy engine の fetch に渡します。GPU plan sink がない、またはその容量条件に入らない経路ではこの環境変数を使った補正はありません。

環境変数自身によるログやエラー出力はありません。`docs/DETAILS.md` は `STRATA_PIN_BY_NEED` と組み合わせたケースを説明し、RTX 3090 + Ryzen 5 5600X の記録として、prompt read が 56K–117K tokens で +5–7%、`--adapt-async 1` と `--pcie-frac 0.6` の decode level が +2–3% と記しています。これは文書に記載された特定条件の測定値で、一般的な性能保証ではありません。

## 根拠

- `src/core/expert_source.cpp:3680-3681,3721-3722,3743-3745,3770-3776`: 関数、miss 数え上げ、PCIe 条件、通常 share と環境変数による補正。
- `src/core/expert_source.cpp:3801-3815,3832-3853`: pinned blob の確認、staging 上限、PCIe plan 作成と fetch。
- `src/core/expert_source.cpp:3502-3513,3525-3529`: file-backed source の pinned 判定と layer 単位の PCIe 可否。
- `include/strata/core/expert_source.hpp:455-459,501-502`: `pcie_num` の意味と dispatch 宣言。
- `docs/DETAILS.md:188-194`: pin-by-need との関係、および記載された測定条件・結果。
