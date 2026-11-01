# `--kv-grow`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 調査）。調査対象リポジトリの `git status --short --branch` は `## main...origin/main`。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--kv-grow` |
| 別名 | なし。無効化用の独立 option `--no-kv-grow` あり |
| 値 | 値なしのフラグ |

## 役割

QSA の K/V cache 用 VRAM を、起動時に `--max-context` 全体ぶん物理確保する代わりに、要求が使う cell 数に合わせて段階的に割り当てます。必要な VRAM は expert cache の slot を空けて K/V に渡し、短い要求の後は一部を expert cache に返して profile 上位の expert を補充します。K/V が保持できる論理上限は `--max-context` のままです。ソースの説明では slot の address を移動しないため、captured graph の参照を保つ設計です（`src/program/generate.cpp:8794-8800`）。

## 使い方

engine の引数例です。`--tokens` は必須で、profile は `--expert-profile` で指定します。

```sh
./strata --pack ./pack --tokens "1,2,3" --expert-profile ./profile.bin --kv-grow
```

engine usage は `strata generate --pack DIR --tokens "1,2,3" [options]` の形を示しています（`src/program/generate.cpp:930-936`）。

## 値と既定値

- parser は値を読み取らず `--kv-grow` で有効、`--no-kv-grow` で無効にします。同じ実行引数に両方あれば、parser の走査順で後に現れた方が `kv_grow` の値になります（`src/program/generate.cpp:3067-3070`）。
- 既定値は無効です（`src/program/generate.cpp:606`）。
- `STRATA_KV_GROW` が空でない場合は CLI 値を上書きします。先頭文字が `0` なら無効、それ以外なら有効です。未設定または空文字なら CLI 値を使います。したがって `STRATA_KV_GROW=0` は `--kv-grow` を打ち消し、`STRATA_KV_GROW=1` は `--no-kv-grow` を打ち消します（`src/program/generate.cpp:5943-5946`）。
- 初期割当量は `STRATA_KV_GROW_INIT` の正の整数値、または既定の 16384 cells です。増分・cache の下限 slot 数はそれぞれ `STRATA_KV_GROW_STEP`（既定 8192 cells）と `STRATA_KV_GROW_FLOOR`（既定 128 slots）で、正の値だけが採用されます（`src/program/generate.cpp:5955-5956`, `8815-8818`, `src/core/layer.cpp:625-626`）。これらの環境変数の個別仕様は [`STRATA_KV_GROW`](../../../envvars/STRATA_KV_GROW.md)、[`STRATA_KV_GROW_INIT`](../../../envvars/STRATA_KV_GROW_INIT.md)、[`STRATA_KV_GROW_STEP`](../../../envvars/STRATA_KV_GROW_STEP.md)、[`STRATA_KV_GROW_FLOOR`](../../../envvars/STRATA_KV_GROW_FLOOR.md) を参照してください。

## 実行時の動作

parser 受理後、起動時に次のすべてを満たす場合だけ elastic K/V を有効にします: 有効化が要求されていること、単一 GPU、`--kv-resident` が 0 以下（全 K/V を VRAM に置くモード）、`--expert-profile` の指定、resident CPU expert mode でないこと、expert cache が 0 でないこと、remote expert cache がないこと、VMM が利用可能であること、`--batch 0`、`--vram-elastic` 無効、`--peer-device` 無効。条件の判定と不成立時の警告は `src/program/generate.cpp:5940-5957` にあります。さらに実際の初期化には VMM range、residency table、RAM 上の expert residency、expert source がそろい、cache slot 数が floor より大きい必要があります（`src/program/generate.cpp:8810-8813`）。

起動時には仮想 range を予約し、初期 cells 分だけ K/V pool を map します。要求長に応じて cells を `STRATA_KV_GROW_STEP` 単位に切り上げ、必要な pool を増やします。増加前に device work を静止させ、profile の下位 expert slot を空け、より上位の resident expert を空いた slot へ移せる場合は移し、必要な chunk を K/V に割り当てます（`src/program/generate.cpp:8828-8835`, `8856-8890`, `src/core/layer.cpp:654-675`）。通常の要求、park 済み会話の復元、session file の復元からも必要量に応じた grow が呼ばれます（`src/program/generate.cpp:14141-14147`, `14520-14526`, `13818-13827`）。

要求が短くなり、park 済み会話が必要とする長さも下回る場合は K/V を縮小し、解放した VRAM を expert cache に戻して profile 順に補充します（`src/program/generate.cpp:8937-8947`, `8964-9005`）。session file 復元時に grow できなければ復元を拒否します。復元後の device transfer 失敗では stdout に `FATAL` を出して engine は終了します（`src/program/generate.cpp:13818-13836`）。

## 適用条件と副作用

- `--kv-grow` を要求しても上記の起動条件を満たさなければ無効のまま進み、stderr に `--kv-grow is off (...)` の警告を出します（`src/program/generate.cpp:5952-5954`）。Metal、gfx906、ROCm 6 未満、または `STRATA_HIP_VMM=0` など VMM 非対応時も利用できません（`src/core/vmm.cpp:154-158`）。
- K/V が増えると GPU expert slot が減り、profile に従って保持されなかった expert は RAM から CPU 計算に回る場合があります。profile が参照する expert data を RAM から読むため、CPU/RAM 側にも依存します（`src/program/generate.cpp:8794-8800`, `5940-5948`）。
- 初期 pool の予約・map/clear や後続の grow が VRAM 不足等で失敗することがあります。pool の map/clear エラーは stderr に出ます（`src/core/layer.cpp:654-675`, `833-835`）。grow 失敗時も stderr に理由を表示し、呼び出し元の要求処理は失敗終了します（`src/program/generate.cpp:8917-8935`, `14142-14147`）。
- 実行統計が有効な経路では、最終 K/V cells 数、grow/trim 回数、手放した expert 数、補充数を stdout に表示します（`src/program/generate.cpp:19005-19008`）。

## 出力とエラー

起動条件を満たさない場合の無効化警告はエラー終了とはせず、通常の割当経路に進みます。実行中の prompt grow 失敗は stdout に `ERR the K/V cannot grow to this prompt: no VRAM is left` を出して終了コード 1、park 済み会話の grow 失敗も同様にエラー出力して終了します（`src/program/generate.cpp:14142-14147`, `14522-14526`）。引数自体に値を付ける option ではなく、`--kv-grow` 固有の値 validation はありません。未知の引数は stderr に `unknown argument`、usage を出して parser が拒否します（`src/program/generate.cpp:3374-3378`）。

## 根拠

- parser と既定値: `src/program/generate.cpp:606`, `3067-3070`。
- 表示される option 説明: `src/program/generate.cpp:960-963`。
- 有効化条件・環境変数上書き・初期化: `src/program/generate.cpp:5940-5957`。
- grow/trim の動作・失敗経路: `src/program/generate.cpp:8794-8935`, `8937-9006`。
- K/V pool の VMM map と初期化: `src/core/layer.cpp:624-675`, `680-683`, `813-835`。
- VMM 対応範囲: `src/core/vmm.cpp:154-158`。
- option の索引と root scope: `docs/cli/README.md:1151-1158`。

GPU/backend ごとの動作確認、ビルド、実行試験は行っていません。記述は上記 commit のソースに基づきます。
