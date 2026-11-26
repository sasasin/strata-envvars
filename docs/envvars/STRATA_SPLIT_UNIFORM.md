# `STRATA_SPLIT_UNIFORM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve --layer-split auto` の配置探索で、各 GPU の PCIe host-to-device 帯域に応じて expert cache miss cost に掛けるリンク別倍率を、すべて `1.0` にします。モデルの配置探索が使う予測値を変える設定であり、実際の PCIe 帯域測定や prompt transfer の設定値を変更する処理ではありません。探索結果や起動可能性により最終配置が変わることはありますが、この変数自体が token の生成方法を変える分岐はありません。読み取りと適用は `engine/src/program/generate.cpp` の自動 layer split 探索内です（`generate.cpp:6990-7013`）。

## 値と判定

`std::getenv` の戻り値が null でなく、文字列の先頭 byte が文字 `'1'` の場合だけ有効です。文字列全体の parse や比較ではありません。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 自動 layer split の探索に到達 | 通常の link miss scaling を使う | `1`, `10`, `1anything` | 空文字、`0`, `true`, `false`, ` 1`, `01` |

空文字は設定済みですが先頭が `'1'` ではないため無効です。大文字小文字や数値としての妥当性は検査せず、先頭一文字のみを見ます。未設定・無効値では通常の倍率が使われます。条件に応じた別の既定値はありません（`engine/src/program/generate.cpp:7003-7011`）。

## 有効になる条件

- `--layer-split auto` を `--serve` と共に指定し、自動 split の初期検査を通過する必要があります。layer split は serve 時だけ有効です（`engine/src/program/generate.cpp:4775-4805`）。
- 実際に複数 GPU の自動配置探索まで進む必要があります。可視 GPU が 1 枚なら `--layer-split auto: one GPU visible, so no split` を出して auto split を解除し、`multi_gpu && split_auto` が偽なら対象変数を読むコードにも到達しません（`engine/src/program/generate.cpp:4836-4839, 4856-4856, 6959-6959`）。
- `--split-skip-if-fits` により単一 GPU へ切り替わった場合も、自動 multi-GPU 探索には入りません（`engine/src/program/generate.cpp:4856`, コメントは `generate.cpp:6810`）。
- GPU エンジンの共通 `generate.cpp` が対象です。CMake は CUDA / HIP 用の GPU engine を共通ソースから構成し、SYCL と Metal は別プロジェクトです（`engine/CMakeLists.txt:20-32`）。候補名の全検索では SYCL / Metal 実装を含む他の読み取り箇所は見つかりませんでした。
- miss cost 用 link 帯域が得られない（native pack でない場合は `-1.0`）と、通常の `link_miss_scale` 自体が全 stage `1.0` を返します。その場合この変数による倍率変更は実質ありません（`engine/src/program/generate.cpp:6992-7007`, `engine/include/strata/program/split_rules.hpp:160-171`）。
- `STRATA_SPLIT_LINK_ABS` との併用では本変数が優先されます。uniform が真なら倍率を `1.0` にし、偽の場合に限って `STRATA_SPLIT_LINK_ABS` の絶対帯域倍率が適用されます。`STRATA_SPLIT_LINK_MIN` で通常倍率のしきい値を変えていても、uniform が真なら計算済み倍率は上書きされます（`engine/src/program/generate.cpp:7003-7011`）。
- `--layer-split K[,K2...]` の手動配置には自動探索のリンク倍率計算がなく、この変数は読み取られません。`--pcie-frac` は後段の stage prompt share probe を省略しますが、自動探索の候補配置評価は `native_pack` なら別途各 stage の link probe を呼びます。いずれもこの変数を CLI が上書きする分岐ではありません（`engine/src/program/generate.cpp:4780-4782, 6710-6718, 6959-6997`）。

## 実行時の詳細

自動探索は stage ごとの帯域を `link_gbps` に記録し、`split_rules::link_miss_scale(link_gbps, link_min)` で通常の倍率を作ります。その後、環境変数が有効なら各 stage の倍率を `1.0` に上書きします。`predict` は各 stage の「profile にあるが cache に載らない routed mass」に miss cost とこの倍率を掛け、層ごとの処理時間を加算して候補配置を比較します。したがってリンク帯域は測定・ログされても、uniform 指定中は miss cost の stage 間の差には反映されません（`engine/src/program/generate.cpp:6992-7013, 7098-7108`）。

読み取りは `split_uniform` の関数内 `static const bool` 初期化子で行われ、プロセス内で初めてこの探索行に到達した時に一度だけ評価され、その後 cache されます。以降に環境を変更しても同じプロセスの値は更新されません。起動時点で探索に到達しなければ読み取り自体が起きないため、次回起動で初めて適用されます（`engine/src/program/generate.cpp:6959-6960, 7003-7004`）。

## ログと測定値

倍率の上書き後も各 stage について `strata generate: layer split auto: CUDA%d link %.1f GB/s -> miss cost x%.2f` を stderr に出します。有効時は最後の倍率表示が `x1.00` になります。無効・未設定でも同じログ形式で通常倍率を表示します。変数専用の警告、エラー、終了経路はありません。配置探索自体が起動可能な split を得られない場合の終了・fallback はこの設定固有ではなく、自動 split の一般処理です（`engine/src/program/generate.cpp:7008-7013, 7487-7508`）。

Strata の `docs/MULTI_GPU.md:133-137` は x16 + x4 の `auto` でリンク倍率が balanced placement を変えうること、および `STRATA_SPLIT_UNIFORM=1` と `gpu_order: as_given` で各リンクを同じ価格にする設定として記載しています。コード上、`gpu_order` はこの環境変数の判定条件ではなく、文書の例で GPU 順序の変化を避けて比較する組み合わせです。測定値や性能向上は本変数単独の一般的効果として資料に示されていないため記載しません。

## 根拠

- `engine/src/program/generate.cpp:4775-4805` — serve と layer split 指定の検査。
- `engine/src/program/generate.cpp:4836-4856` — 可視 GPU 数、multi-GPU 条件。
- `engine/src/program/generate.cpp:6959-7013` — 適用範囲、link probe、環境値の判定、倍率上書き、ログ。
- `engine/src/program/generate.cpp:7098-7108` — 倍率が候補配置の予測 miss cost に入る箇所。
- `engine/include/strata/program/split_rules.hpp:150-171` — link minimum と通常倍率の計算。
- `engine/CMakeLists.txt:20-32` — 共通 CUDA/HIP と別建て SYCL backend。
- `docs/MULTI_GPU.md:133-137` — Strata の利用者向け説明。
