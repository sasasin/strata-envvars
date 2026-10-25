# `--resident-budget-gib`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat` 等からも委譲） |
| オプション | `--resident-budget-gib` |
| 別名 | なし |
| 値 | `N`。GiB 単位の正の数（`float`） |

## 役割

対応する Unsloth モデルの setup で、GPU キャッシュにない expert のうち RAM に保持する量を指定します。エンジンは expert profile で利用頻度の高いものから指定予算に収まる分を RAM にコピーし、残りはモデルファイルから読みます。setup の parser help は対象を `UD-Q4_K_XL`、`UD-IQ4_XS` と記載しています（`setup.py:8528-8530`）。

## 使い方

Strata の checkout ルートで、たとえば次のようにモデルと予算を明示して setup します。

```sh
python setup.py --setup --model UD-Q4_K_XL --resident-budget-gib 32 --yes
```

`--setup` は起動ではなくモデルの追加・設定変更を選びます。`--yes` は確認への推奨回答を使いますが、setup が提示するリスク条件をすべて自動承認するものではありません（`setup.py:25-36`）。ラッパーを使う場合も同じ引数が `setup.py` に渡されます（`docs/cli/README.md` の `source-setup` 境界説明）。

## 値と既定値

- `argparse` は値を `float` として読みます。省略時の parser 既定値は `None` で、setup は対象モデルと PC の RAM に応じて予算を決めます（`setup.py:8528-8530`、`setup.py:3111-3117`、`setup.py:3167-3178`）。
- setup の通常経路では `N <= 0` を `ap.error` で拒否します。数値でない値は `argparse` の型変換で拒否されます（`setup.py:8565-8566`）。
- 既定の推奨値は概ね `round(RAM GiB) - 24 - ceil(KV streaming RAM GiB)`、最低 8 GiB、上限はモデルの expert サイズです。初期計算の `resident_budget_gib()` は KV 量を引数省略時の 0 として呼びます（`setup.py:3095-3100`）。
- 明示値が推奨値を超えても setup は保持し、RAM 逼迫・低速化の可能性を警告します。setup は上限値を設けず、エンジン起動時の利用可能 RAM 等に応じて clamp します（`setup.py:3167-3178`、`src/core/expert_source.cpp:3515-3542`）。
- 小数値も許可され、整数でない場合は小数のまま設定引数へ書き出されます（`setup.py:3167-3178`、`setup.py:9507-9508`）。

## 実行時の動作

- 対象モデルで RAM 予算モードになるのは、明示値がある場合、統合メモリ GPU の場合、または全 expert と追加 16 GiB が RAM に収まらない場合です（`setup.py:3103-3117`）。明示値があればその値を `budget_choice()` が採用します。
- setup は選んだ予算を設定の `args` に `--resident-budget-gib N` として追加します（`setup.py:9507-9508`）。長い context の KV streaming が有効な場合、KV cache 用 RAM を推奨予算から差し引きます。ただし明示予算は維持し、KV 用 RAM がその上に加わると警告します（`setup.py:9484-9500`）。
- 統合メモリ GPU では予算と GPU expert cache が RAM を共有します。setup は残り RAM から expert-cache slot 数を設定できる場合は `auto` を数値に変更し、余裕がない場合は `auto` のまま警告します（`setup.py:9509-9520`、`setup.py:3154-3164`）。
- 対象外のモデルで指定すると setup は「UD-Q4_K_XL と UD-IQ4_XS 向け」と警告し、そのモデル用の実行引数にはこの option を追加しません（`setup.py:9028-9030`）。
- 非対応の複数 GPU layer split を選んだ場合、予算を削除して全 expert を RAM に載せる構成に切り替える経路があります。engine が split での resident budget に対応する場合は予算を維持します（`setup.py:1894-1918`、`setup.py:5786-5829`）。
- エンジン parser は値を byte に換算し、`--mmap-experts`、resident CPU expert、page pinning を有効にし、標準 headroom を 4 GiB にします。`STRATA_RESIDENT_PIN=0` は pinning を止め、`STRATA_RESIDENT_HEADROOM_GIB` は有効な非負値なら headroom を置き換えます（`src/program/generate.cpp:2767-2776`）。
- 実際に保持するのは GPU cache にない expert のうち、profile の順位で予算内に収まるものです。残りは mapped model files に残ります。Windows では RAM に加えて commit 容量も上限計算に使われます（`include/strata/core/expert_source.hpp:737-740`、`src/core/expert_source.cpp:3515-3549`）。

## 適用条件と副作用

- `setup.py` は macOS の control mode と SYCL backend を一般的な値検査より先に委譲します。そのため、この文書の正数検査・対象モデル別 setup 動作は通常の setup 経路についての説明です（`setup.py:8561-8566`）。
- Setup 設定に値を保存するほか、エンジン起動時に expert を RAM へコピーし、余った expert をモデルファイルから読む構成になります。エンジンは起動時の RAM / commit 状況に応じて予算を clamp し、clamp 時は `stderr` に利用可能容量と調整後予算を出します（`src/core/expert_source.cpp:3515-3542`）。
- RAM が少ない場合でも setup は大きな明示値を保持します。setup は paging や under load の RAM 枯渇リスクを警告し、予算を実際に確保できない場合、エンジンは全 expert をファイルから読む fallback にします（`setup.py:3173-3178`、`src/program/generate.cpp:8275-8281`）。
- 予算が保持できないこと自体はエンジンの終了理由にせず、警告を出して続行します。利用可能メモリを判定できない場合は resident 構築が失敗し、この予算モードでも fallback 警告の経路に入ります（`src/core/expert_source.cpp:3519-3523`、`src/program/generate.cpp:8275-8281`）。
- 予算モードでは file tier が unbuffered I/O を選ぶ処理があり、その選択結果を engine が `stderr` に出力します（`src/program/generate.cpp:5725-5739`）。OS、backend、ファイル配置ごとの実際の I/O 性能はこのソース調査では評価していません。

## 出力とエラー

- 値が数値でない場合は `argparse` の型エラー、通常経路で 0 以下なら `--resident-budget-gib takes a number of GiB above 0` を表示して引数エラーになります（`setup.py:8528-8530`、`setup.py:8565-8566`）。`argparse.ArgumentParser.error()` による通常の usage/error 終了です。
- setup が推奨より大きい値を保持する際は、OS・engine・file cache の余裕が減り、低速化または負荷時の RAM 枯渇があり得る旨を警告します（`setup.py:3173-3178`）。
- engine は予算 clamp の場合に調整内容を `stderr` に表示します。予算を確保できない場合も `stderr` の WARNING を出し、残りを model files から読みます（`src/core/expert_source.cpp:3528-3542`、`src/program/generate.cpp:8275-8281`）。
- Engine parser 自体も `N > 0` を確認し、違反時は `strata generate: --resident-budget-gib needs N > 0` として終了コード 2 を返します（`src/program/generate.cpp:2767-2770`）。

## 根拠

- Setup parser と正数 validation: `setup.py:8528-8530`、`setup.py:8561-8566`。
- 推奨値、対象モデルの判定、明示値の警告: `setup.py:3095-3117`、`setup.py:3167-3178`。
- 対象外モデルの扱い、設定引数への追加、KV / UMA 相互作用: `setup.py:9028-9030`、`setup.py:9484-9520`。
- Engine parser と実行時の resident budget 処理: `src/program/generate.cpp:2767-2776`、`src/core/expert_source.cpp:3515-3549`、`src/program/generate.cpp:8275-8281`。
- Engine の profile 順 resident selection: `include/strata/core/expert_source.hpp:737-740`。
