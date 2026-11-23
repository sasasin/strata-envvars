# `strata --expert-profile`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root scope） |
| オプション | `--expert-profile` |
| 別名 | なし |
| 値 | profile ファイルのパス（文字列） |

## 役割

MoE expert の `(layer, expert)` 順位表を起動時に読み、順位の高い expert を expert cache に先行配置する。profile を指定しない場合の初回利用順による配置に代わり、profile 順を cache 配置ポリシーとして使う。オプションは `engine/src/program/generate.cpp:4206` で値を受け取り、profile 読み込み後に `engine/src/program/generate.cpp:9671-9674` の一度限りの tier fill へ渡される。

## 使い方

```sh
strata --native model.gguf --expert-profile profile.bin
```

profile は起動時に読み込まれる。`--expert-cache N` を併用して順位リストの先頭から使う cache 容量を明示できる。例として `--expert-cache 2048` は読み込み済み順位の先頭から 2048 slot 分を対象にする。profile を指定して `--expert-cache` を省略するか `0` にすると、エンジンは自動 sizing に切り替える（下記「実行時の動作」参照）。

## 値と既定値

- `--expert-profile` は次の argv 要素をそのままパスとして受け取る。値の形式・拡張子を parser では検査せず、ファイル内容は読み込み時に検査する（`engine/src/program/generate.cpp:3837-3842,4206`）。同じ引数を複数回指定した場合、parser は都度同じフィールドへ代入するため最後の指定が残る（同 `:3837-3842,4206`）。
- 既定値は空文字列で、profile を使わない（`engine/src/program/generate.cpp:926-930`）。空文字列を明示した場合も空のままで、読み込み処理は行われない（同 `:6718-6723`）。
- profile はバイナリ形式で、先頭の magic は `STRP`、version は 1、header の layer 数と expert 数は実行モデルと一致しなければならない。header に記録された slot 数以上の順位ペアは許可されず、順位ペアの layer / expert index もモデル範囲内である必要がある（`engine/src/core/expert_cache.cpp:177-243`）。
- `--expert-cache` を明示して正数を指定すると、その値で profile 順位を切り詰める。profile 指定時に値が 0（既定値を含む）なら `-1` に変換して自動 sizing として扱う（`engine/src/program/generate.cpp:6725-6728`）。cache 容量より profile の順位ペアが少ない場合は profile 長が上限になる（同 `:9417-9424`）。

## 実行時の動作

`read_expert_profile` はパスを `rb` で開き、header と順位ペアを読み込んでモデルの layer 数・expert 数、version、slot 数、ペアの範囲を検証する（`engine/src/core/expert_cache.cpp:177-243`）。profile は順位表であり、expert の重み本体は選択中のモデル artifact から cache に読み込まれる。

読み込んだ順位は expert cache の先行 fill に使われる。通常の全体 cache では順位先頭から `min(profile の長さ, cache slots)` 件を対象とし、各ペアを cache に admit して model source から読み、slot に格納する。per-layer admission が有効な場合は全順位を走査し、各 layer の slot 範囲が満杯になったペアを飛ばす（`engine/src/program/generate.cpp:9680-9689,9708-9728`）。fill は起動時に一度行われ、その後は profile 外の expert は cache miss として処理される（同 `:9671-9674`）。

`--expert-profile` は他の設定にも条件として使われる。複数 GPU の layer split では必須で、未指定なら stderr にエラーを出して終了コード 2 で戻る（`engine/src/program/generate.cpp:4890-4894`）。`--resident-cpu-experts` との併用では `--mmap-experts` も必要（同 `:4865-4867`）。一方 `--cpu-oracle-q8-0` とは併用できず、指定すると stderr に理由を出して終了コード 2 となる（同 `:5294-5296`）。また、profile がない場合は `--prefill auto` が通常の auto ではなく小さい固定 chunk にフォールバックする（同 `:4985-4989`）。

## 適用条件と副作用

- 指定した profile を起動時に読み込むため、そのファイルへの読み取りアクセスが必要。読み込み後、起動時に順位ペアのモデル重みを expert cache へ fill する（`engine/src/core/expert_cache.cpp:179-186`; `engine/src/program/generate.cpp:9708-9728`）。このオプション自体は profile ファイルを書き換えない。
- profile は現在選択しているモデルの layer 数と expert 数に結び付く。異なる layout のモデル用 profile は拒否される（`engine/src/core/expert_cache.cpp:209-216`）。
- 複数 GPU layer split と `--resident-cpu-experts` では上記の必須条件がある。Qwen3.6 専用 parser にも同名オプションが索引上別 scope で存在するが、この文書は索引の `strata-engine/root/`、すなわち `engine/src/program/generate.cpp` の parser を対象にする（`docs/cli/README.md:1036-1040,1240-1254`; `docs/cli/000_cli_tools.md:10`）。
- 実際に使える backend/build と GPU cache の挙動は実行バイナリの build 条件に依存する。本調査ではビルドや GPU 実行を行っていないため、個別 backend の実行可否や所要時間は確認していない。

## 出力とエラー

- 値が省略されると parser が `<option> needs a value` を stderr に出し、終了コード 2 で終了する（`engine/src/program/generate.cpp:3839-3841`）。
- ファイルを開けない、header 不足、magic 不一致、version 不一致、モデル layout 不一致、順位数が slot 数を超過、順位リストの切り詰め、範囲外ペアは `read_expert_profile` がエラー文字列を返す。呼び出し側は `strata generate: <理由>` を stderr に出し、終了コード 1 を返す（`engine/src/core/expert_cache.cpp:179-240`; `engine/src/program/generate.cpp:6719-6724`）。
- 起動時 fill 中に model source の重み取得・slot 格納が失敗すると、`strata generate: the profile fill failed at pair ...` を stderr に出して終了コード 1 を返す（`engine/src/program/generate.cpp:9720-9727`）。

## 根拠

- `engine/src/program/generate.cpp:926-930` — フィールドの既定値と profile の用途。
- `engine/src/program/generate.cpp:3837-3842,4206` — parser の値取得、未指定値エラー、root parser での登録。
- `engine/src/program/generate.cpp:4865-4867,4890-4894,4985-4989,5294-5296` — `--resident-cpu-experts`、layer split、prefill auto、CPU oracle との相互作用。
- `engine/src/program/generate.cpp:6718-6760` — profile 読み込み、自動 cache sizing、peer 用順位調整、読み込みログ。
- `engine/src/program/generate.cpp:9671-9728` — 起動時 cache fill の対象数、順序、重みの読み込み、fill エラー。
- `engine/src/core/expert_cache.cpp:177-243` — バイナリ profile の読み込みと検証条件。
- `docs/cli/README.md:1036-1040,1240-1254`、`docs/cli/000_cli_tools.md:10` — 対象 tool ID と root scope、および Qwen3.6 専用 parser との区別（索引情報であり、挙動根拠ではない）。

調査範囲は上記 checkout の parser と Strata 所有の読み込み・cache fill 実装。backend ごとの build 条件、実機での GPU 動作、profile 作成ツールの詳細はこの文書では検証していない。
