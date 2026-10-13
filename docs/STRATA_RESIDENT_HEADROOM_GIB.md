# `STRATA_RESIDENT_HEADROOM_GIB`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

常駐RAMモードで、GPUキャッシュにない expert をホストRAMへコピーするときに、利用可能RAMから差し引いて残す安全余裕量をGiB単位で指定します。生成エンジンでは `--resident-experts` と `--resident-budget-gib N` の引数処理時に読みます。通常の mmap 読み込みだけの実行ではこの値は読みません。

## 値と判定

対象値を文字列全体として検証するのではなく、Cライブラリの `std::atof` で `double` に変換し、結果が `>= 0.0` のときだけ採用します。採用値に `1073741824.0`（2^30）を掛け、`uint64_t` にキャストしてバイト数にします。小数GiBを指定でき、バイトへのキャスト時に小数部は切り捨てられます。上限値への clamp はありません。

| 入力 | 挙動 |
|---|---|
| 未設定 | 4 GiBを使用 |
| `0`、空文字、数値に変換できない文字列 | `atof` の結果が0となり、0 GiBを採用 |
| `2.5` | 2.5 GiBを採用 |
| 数字の後ろに文字が続く値（例: `2.5GiB`） | `atof` が認識する数値接頭部を採用 |
| 負数（例: `-1`） | `>= 0.0` を満たさず、4 GiBの既定値を維持 |
| `nan` | 比較が偽になり、4 GiBの既定値を維持 |

`atof` は変換エラーを別途報告しないため、不正な文字列も通常は0として扱われます。正の無限大や `uint64_t` の範囲を超える数値について、コードに明示的な上限検査はありません。範囲外の浮動小数値を整数型へ変換した場合の結果は保証されないため、通常の有限で非負のGiB値を指定してください。

この同じ判定は各CLI引数の処理中に行われ、`--resident-experts` または `--resident-budget-gib` が現れるたびに環境値を読みます。設定有無の判定だけではなく数値変換するため、空文字も既定値維持ではなく0として有効です。

## 有効になる条件

- `--resident-experts` は mmap-backed expert 読み込みと resident RAM コピーを有効化します。全 complement が余裕量を残して収まらないときは、収まる範囲のhot expertだけを残す再試行があり、それもできなければ mmap 読み込みに戻ります。
- `--resident-budget-gib N` はRAM内に保持するexpert量の予算を指定し、その実装でも本環境変数を読む。要求予算は利用可能メモリから余裕量と0.25 GiBのmarginを差し引いた範囲にclampされます。確保できない場合、GPUにないexpertはファイルから読み込むfallbackになります。
- `--resident-cpu-experts` 単独の引数処理ではこの環境変数を読みません。オプション構造体の初期値は8 GiBですが、上記2引数は処理時に明示的に4 GiBへ設定し、その後この環境変数で上書きします。
- CUDA/HIPの生成経路とSYCL生成経路に同じ値の読み取りとresident安全枠への受け渡しがあります。対象GPUや実行モードの制約によりresident RAMモード自体が起動しない経路には効果がありません。

## 実行時の詳細

CLI引数解析中に値を読み、オプション構造体の `resident_headroom` に保存します。実行開始後やリクエストごとの再読込はなく、プロセス起動中に環境値を変更しても反映されません。常駐コピー計画では、expertの配置計画後に利用可能メモリを調べ、RAMとcommitのうち小さい方から余裕量を引いて安全予算を計算します。Linuxでは `MemAvailable` を基にし、可視なcgroup制限も考慮します。Windowsでは利用可能な物理RAMとcommit容量の小さい方が上限になります。

headroomを差し引いた枠に全expert complementが収まらなければ、`--resident-experts` はhot expertだけを保持するsoft fallbackを試みます。コピーが成立した場合はresident量とRAM内に保持できたprompt貸出slot数をstderrに出します。prompt貸出slotのexpertが不足したときは `STRATA_RESIDENT_HEADROOM_GIB` を下げて再起動する案内を含む警告をstderrに出します。resident copy自体が成立しない場合は mmap/file読み込みfallbackになり、budgetモードでは不足警告が出ます。

Linuxでpage-lockを要求する場合、この値は `STRATA_PIN_RESERVE_GIB` が正の値を指定していないとき、段階的なpage-lock中に残すRAM reserveの既定値にも使われます。ただしこのreserveは最低2 GiBに引き上げられます。`STRATA_PIN_RESERVE_GIB` の正の値があればそちらを使い、`STRATA_PIN_GUARD=0` なら段階的なpage-lockを無効にします。このpinning側のreserve規則は、resident copyの大きさを決めるheadroom予算とは別です。

`setup.py` は、resident関連引数がありRAMが48 GB以下のとき、`env` 辞書にこのキーが存在しなければ6 GiB設定のtipを出します。ここでは値をparseせず、キーがあるだけでtipを抑制します。この6 GiBはコミュニティ測定に基づく推奨値で、生成エンジンの既定値4 GiBとは別です。

## 文書との照合

`docs/DETAILS.md` は4 GBを残す既定動作を説明しています。`docs/AMD_HIP.md` は常駐RAM量を起動時の `MemAvailable` からheadroomを引いて決めるとし、`--resident-experts` と `--resident-budget-gib` が本変数を読むと記載しており、実装と一致します。資料中の性能値はこの環境変数自体の一般的な効果としては扱っていません。

## 根拠

- `src/program/generate.cpp:2150-2170` — 既定4 GiBの設定、2つの引数分岐での `getenv` / `atof` 判定と単位変換。
- `sycl/src/program/generate.cpp:1958-1979` — SYCL経路の同じ値判定。
- `src/program/generate.cpp:6793-6808,6855-6865` — 安全枠を使ったresidentコピー、soft fallbackとログ。
- `sycl/src/program/generate.cpp:6431-6448` — SYCL経路のresidentコピーとsoft fallback。
- `src/core/expert_source.cpp:326-413,2652-2682,2709-2738` — 利用可能RAM、Windows commit、headroomを引く予算と上限判定。
- `src/core/expert_source.cpp:3178-3197` — resident結果、貸出slot数およびheadroom調整案内のログ。
- `src/core/expert_source.cpp:2822-2857` — Linuxの段階的page-lock時にheadroomを既定reserveとして使う条件と `STRATA_PIN_RESERVE_GIB` による上書き。
- `include/strata/core/expert_source.hpp:555-573` — headroom引数とbudgetの契約。
- `setup.py:4585-4588,4598-4618` — setupの6 GiB tipと環境キー存在判定。
- `docs/DETAILS.md:183-189`, `docs/AMD_HIP.md:227-239` — 文書上の既定値、適用経路と推奨の説明。
