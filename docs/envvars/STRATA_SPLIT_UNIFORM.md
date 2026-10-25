# `STRATA_SPLIT_UNIFORM`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の複数 GPU サーバーで `--layer-split auto` の配置を探索するとき、各 GPU の PCIe link 速度に応じた expert cache miss cost の補正を無効にし、全 GPU の miss cost 係数を `1.0` にします。これは層の割り当てを決める予測値を変える設定です。実行時の PCIe 転送速度や cache miss 自体を変える処理ではありません。

## 値と判定

値全体の parse や数値変換は行わず、`getenv()` が返す文字列の先頭 1 文字を調べます。

| 環境変数の状態・値 | 結果 |
|---|---|
| 未設定 | 無効。通常の link 速度に基づく係数を使う |
| 空文字 | 無効（設定値はあるが先頭文字が `\0`） |
| 先頭文字が `1` | 有効。`1`、`10`、`1anything` などを含む |
| それ以外 | 無効。`0`、`true`、空白始まりなどを含む |

大文字小文字、後続文字、数値としての妥当性は判定しません。値は関数内の `static const bool` に保存されます。この判定箇所へ初めて到達した後、同一プロセス内で環境を変更しても再評価されません。

## 有効になる条件

- `--serve` の layer split 経路で、複数 GPU (`multi_gpu`) かつ `--layer-split auto` (`split_auto`) のときに限り、該当する配置探索ブロックに到達します。手動の層境界指定ではこの判定を通りません。
- 1 GPU しか見えず `auto` が分割なしに切り替わる場合や、`--split-skip-if-fits` により探索前に単一 GPU へ切り替わる場合、この環境変数による配置補正はありません。
- 調査対象リポジトリでは名前の読み取りは CUDA 実装 `src/program/generate.cpp` のみで見つかりました。`sycl/src/program/generate.cpp` にこの変数の読み取りはありません。
- PCIe probe 値が得られない stage は標準の `link_miss_scale()` でも係数 `1.0` になります。その stage の係数については、この環境変数による差はありません。

## 実行時の詳細

自動配置の予測では、まず `link_miss_scale()` が各 stage の H2D link 速度を比較します。最速 link との比が 4 倍以上なら、遅い stage の係数を比率（最大 64）にし、それ未満なら `1.0` のままにします。`STRATA_SPLIT_UNIFORM` が有効なら、その後すべての係数を `1.0` で上書きします。

この係数は各 stage の未 cache 率に掛けられ、miss cost の予測値へ加算されます。探索が選ぶ配置に影響することがあります。`STRATA_SPLIT_LINK_ABS` が同時に設定されていても、uniform が有効なら uniform 側が優先されます。`STRATA_SPLIT_MISS_MS` による全体の miss cost 倍率は別に使われ、uniform にしても無効化されません。

ログには各 stage について `strata generate: layer split auto: CUDA%d link %.1f GB/s -> miss cost x%.2f` が出て、適用後の係数を確認できます。

## 文書と測定値

`docs/MULTI_GPU.md` はこの設定を opt-in とし、`"gpu_order": "as_given"` と併用して各 link を同じ価格で扱う方法として説明しています。同資料は 2x RTX 3090 の x16 + x4 構成で、自動配置が K=31（miss cost x4.20、decode 114–119 tok/s）から K=27（130–136 tok/s）へ変わった事例を記載しています。これは同資料の報告値であり、他の構成で同じ配置や性能になることを示すものではありません。

## 根拠

- `src/program/generate.cpp:2779-2811` — `auto` 指定、serve 条件、multi-GPU 判定。
- `src/program/generate.cpp:3942-3972,4321-4322` — `split-skip-if-fits` による探索回避と自動配置ブロック。
- `src/program/generate.cpp:4352-4375` — link 速度の取得、環境変数判定と優先順位、stage 係数ログ、miss cost 倍率。
- `src/program/generate.cpp:4458-4467` — stage ごとの miss 率と係数を予測コストに反映。
- `include/strata/program/split_rules.hpp:129-149` — 通常時の link miss scale の閾値と上限。
- `docs/MULTI_GPU.md:80-82` — 設定の説明と記載された測定事例。
