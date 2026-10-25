# `--vram-elastic`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、root） |
| オプション | `--vram-elastic` |
| 別名 | なし |
| 値 | 取らないフラグ。指定で有効化を要求する |

## 役割

サーバー実行時に GPU 上の expert cache を単一の `cudaMalloc` ではなく複数の CUDA 仮想メモリ segment で確保します。これによりサーバーが要求を処理していない間、後述の `VRAM` 操作で cache の末尾 segment を解放し、必要に応じて再マップできます。dense weights、K/V、その他の GPU メモリ全体を解放する機能ではありません（`src/program/generate.cpp:613-616,11197-11204`、`src/core/expert_cache.cpp:216-218`）。

## 使い方

```sh
strata --pack ./my-pack --serve --tokens "1,2,3" --vram-elastic
```

エンジンの usage は `strata generate --pack DIR --tokens "1,2,3" [options]` を示し、`--serve` は常駐サーバーモードです。実際の pack と prompt の指定は利用環境に合わせてください（`src/program/generate.cpp:806-812,2633-2638`）。

segment サイズを指定する場合は別 option を併用します。

```sh
strata --pack ./my-pack --serve --tokens "1,2,3" --vram-elastic --vram-segment-mib 512
```

## 値と既定値

`--vram-elastic` は引数 parser で boolean を `true` にするだけで、値は取りません。省略時は `false` で、expert cache は通常の単一 allocation 経路です（`src/program/generate.cpp:615,2604`）。

segment サイズは `--vram-segment-mib` で別途指定し、省略時は 512 MiB です。値は `atoll` で整数化され、厳密な数値形式・上限の parser validation はありません。64 MiB 未満なら feature を無効化して警告します。したがって 0、負数、整数として読めない値もこの判定により無効化されます（`src/program/generate.cpp:616,2605,6284-6297`）。CUDA driver の推奨 allocation granularity に合わせ、実際の segment は必要に応じて切り上げられます（`src/core/expert_cache.cpp:313-321`）。

## 実行時の動作

起動時に `--serve` でない、layer split による複数 GPU、remote/helper expert cache の利用、segment が 64 MiB 未満、または HIP build のいずれかに該当すると、stderr に `strata generate: --vram-elastic is off: ...` を出し、この指定を無効にして通常の cache allocation に進みます。これらは当該 option の起動拒否ではありません（`src/program/generate.cpp:6282-6298`）。

条件を満たす場合は segment サイズを byte 単位にして expert cache に設定し、cache を segment allocation で開きます。要求した reserve に応じて server の `VRAM` 操作が cache の末尾を unmap し、再拡張時には map し直します。縮小で cache から外れた expert は CPU 側の miss として扱われ、拡張時は slot を再充填します。縮小・拡張は自動ではなく操作を受けたときだけ実行されます（`src/program/generate.cpp:6297,11197-11204,11247-11301`、`src/core/expert_cache.cpp:384-414,418-468`）。起動時の INFO 行には `vram_elastic=1` または `0` が出力されます（`src/program/generate.cpp:11078-11096`）。

`--kv-grow` と同時に要求すると、`--kv-grow` の適用条件から `!o.vram_elastic` が外れるため KV の伸長機能は無効になり、stderr に `--kv-grow is off ... no --vram-elastic ...` と出ます（`src/program/generate.cpp:5202-5213`）。

## 適用条件と副作用

- 起動時に有効となるのは `--serve`、単一 GPU、helper cache なし、segment 64 MiB 以上、CUDA build の組み合わせです（`src/program/generate.cpp:6284-6297`）。
- Driver の仮想メモリ管理 API が利用できない、GPU が VMM をサポートしない、granularity の取得や仮想アドレス範囲の確保に失敗する場合は cache open に失敗します（`src/core/expert_cache.cpp:297-325`）。
- 初期 segment の確保失敗時は解放処理を行って cache open を失敗させます（`src/core/expert_cache.cpp:329-342`）。engine 側はエラーを stderr に出して終了コード 1 を返します（`src/program/generate.cpp:6361-6390`）。HIP build では通常、起動時条件判定で無効化されます。低 RAM resident mode は起動時の無効条件ではありませんが、実行中の `VRAM` 操作は resident low-RAM mode と併用できずエラーになります（`src/program/generate.cpp:11227-11235`）。
- `VRAM` 操作は batch decode 中や prompt buffer の loan が残る間も拒否されます。GPU 同期に失敗した場合もエラーになります（`src/program/generate.cpp:11236-11242`）。
- この option は expert cache の領域管理だけを切り替えます。reserve 操作では実際の free VRAM により希望値に届かない場合があり、cache は prompt path が必要とする最低 slot 数を残すことがあります（`src/program/generate.cpp:11245-11260`）。

## 出力とエラー

無効条件では stderr に理由付きの `--vram-elastic is off` 警告を出して継続します。VMM 初期化・allocation の失敗は `ExpertCache: ...` の内容を stderr に出し、engine は終了コード 1 を返します（`src/program/generate.cpp:6293-6297,6384-6390`、`src/core/expert_cache.cpp:297-342`）。未知の引数は別経路で usage と `unknown argument` を stderr に出し、終了コード 2 です（`src/program/generate.cpp:2787-2792`）。

## 根拠

- parser、既定値、関連 help 記述: `src/program/generate.cpp:613-616,907-910,2604-2605`
- 起動条件と無効化: `src/program/generate.cpp:6282-6298`
- segmented cache の初期化・driver 要件: `src/core/expert_cache.cpp:297-345,471-508`
- cache の縮小・拡張と `VRAM` 操作: `src/core/expert_cache.cpp:384-414,418-468`、`src/program/generate.cpp:11197-11242,11245-11314`
- `--kv-grow` との相互作用: `src/program/generate.cpp:5200-5213`
- 起動ログと allocation failure: `src/program/generate.cpp:6361-6390,11078-11096`

この文書は指定 checkout のソースを確認した結果です。同一 revision の engine バイナリや Release 配布物での `--help` 照合は行っていません。
