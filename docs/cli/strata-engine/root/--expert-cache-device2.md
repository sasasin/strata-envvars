# `strata --expert-cache-device2`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。サブコマンドなし） |
| オプション | `--expert-cache-device2` |
| 別名 | なし |
| 値 | `N` または `auto`。`N` は CUDA2 helper cache に割り当てる expert 数、`auto` は空きメモリに収まる数 |

## 役割

2 番目の helper GPU（既定の device 配置では CUDA2）に、primary と先行する helper cache が持たない expert を保持する上限を指定する。これは helper GPU が primary の dense weights や state を持つ layer split ではなく、profile に基づく追加 expert cache を作る設定である。`STRATA_PRIMARY_DEVICE` で primary を変更した場合、helper 番号は primary 以外の可視 device の順序に対応する。実際に有効にするには、先行する `--expert-cache-device1` に加えて、primary cache、expert profile、および expert pool が必要になる。

## 使い方

```sh
# CUDA1 と CUDA2 に、それぞれ上限 2048 個の追加 expert cache を設定
strata --expert-cache 4096 --expert-profile profile.txt \
  --expert-cache-device1 2048 --expert-cache-device2 2048 --tokens tokens.txt

# CUDA2 は 512 MiB の空き領域を残しながら収まる数を自動選択
strata --expert-cache 4096 --expert-profile profile.txt \
  --expert-cache-device1 2048 --expert-cache-device2 auto --tokens tokens.txt
```

## 値と既定値

- オプションを省略したときの CUDA2 cache 数は `0`（無効）。構造体の初期値は全 helper の slot 数が `0`。
- 数値は `std::atoi` で整数化され、負数は後段の resource parameter 検査で拒否される。`0` は受理されるが CUDA2 cache は作らない。整数以外の文字列も `atoi` の結果が使われるため、先頭が数値でない値は `0` として扱われる。
- `auto` は内部で `INT_MAX` と `auto` 指定フラグに変換される。cache 初期化時に、expert blob の必要量を見積もり、CUDA2 の空きメモリから 512 MiB を残す範囲で選ぶ。該当する expert が 1 件も収まらない場合は起動失敗となる。
- 数値を指定した場合は上限個数を選び、空きメモリ不足でも自動で数を減らさない。割り当て後に 512 MiB 未満しか残らない見積もりなら失敗する。

## 実行時の動作

parser は `--expert-cache-device1` / `2` / `3` を共通分岐で受け取り、末尾の数字から配列位置を決める。したがって device2 は `expert_cache_remote[1]` と `expert_cache_remote_auto[1]` に設定される。既定では helper 番号 2 は CUDA device ordinal 2 だが、`STRATA_PRIMARY_DEVICE` が指定されると primary を除いた可視 device の順に割り当てられる。指定回数が複数なら parser が順に代入するため最後の指定が残る。

値が正の場合、primary の expert profile 順に沿って primary cache が持たない expert を CUDA2 用に選ぶ。複数 helper が有効な場合は `--expert-cache-remote-placement stripe`（既定）なら cache 数の枠に従って helper 間に分配し、`layer` なら layer 番号を helper 数で割った担当に配置する。初期化時には CUDA2 の device context、cache と計算用領域を作り、選択した expert blob を cache に読み込む。helper が計算した結果は pinned host rows 経由で戻される。

## 適用条件と副作用

- CUDA2 を指定するには `--expert-cache-device1` も正数である必要がある。CUDA3 を指定する場合は CUDA2 も正数でなければならない。順序に反すると `invalid sampling or resource parameter` を stderr に出し、終了コード 2 で終了する。
- remote cache 全体を使うには `--expert-cache-device1` が正で、`--expert-cache` が正、`--expert-profile` が指定済み、expert pool が有効でなければならない。満たさない場合は説明を stderr に出し、終了コード 2 で終了する。
- `--peer-device` は helper cache と同時に指定できない。layer split と併用すると、layer split の stage が使わない可視 GPU が helper 用に必要となる。GPU が足りない場合は stderr に理由を出して終了コード 2 となる。
- CUDA2 context、GPU cache、計算 scratch、stream、pinned host staging buffers を確保するため、CUDA2 の VRAM と host pinned memory を消費する。helper cache は primary / stage cache がすでに保持する expert を除外する。
- `auto` は選択する expert 数を空き GPU memory に合わせるが、context や後続 driver allocation などの実使用量と CUDA ドライバの挙動を完全に予測するものではない。初期化・確保に失敗すると、エラーメッセージを stderr に出して終了コード 1 で終了する。

## 出力とエラー

- 起動時に helper context の準備状況を `strata generate: CUDA2 context ready, ... GiB free ...` 形式で stderr に表示する。cache 作成後は追加 expert 数と GiB、pinned host rows 経由で結果を戻す旨を表示する。
- 自動選択時に空きメモリ内に expert が 1 件も入らない場合は `no unclaimed expert fits with 512 MiB free`、固定数が空きメモリを使い切る場合は 512 MiB の余裕がない旨を表示する。GPU が不可視、primary と同じ device、cache allocation / fill / stream 等の失敗も stderr に出て、初期化失敗は終了コード 1 となる。
- serve mode ではリクエストごとの CUDA helper の計算 entry 数、layer launch 数、返却 bytes、staging / launch 時間、待ち時間を stderr に表示する。

## 根拠

- `engine/src/program/generate.cpp:904-907` — helper cache の slot 数、`auto` フラグ、placement の既定値。
- `engine/src/program/generate.cpp:1420-1425` — CLI help にある device1/2/3 と配置方式の説明。
- `engine/src/program/generate.cpp:3988-3993` — option parser、device 番号から配列位置への変換、`auto` と数値の変換。
- `engine/src/program/generate.cpp:5267-5278` — 負数拒否、device1/2/3 の順序制約、配置値検証と終了コード。
- `engine/src/program/generate.cpp:5284-5290` — `--peer-device` との併用拒否。
- `engine/src/program/generate.cpp:4954-4968` — layer split 時に stage が使わない GPU を helper に割り当て、不足時に終了コード 2 とする処理。
- `engine/src/program/generate.cpp:4884-4893` — `STRATA_PRIMARY_DEVICE` が指定されたとき、primary を除いた可視 device を helper 順に対応させる処理。
- `engine/src/program/generate.cpp:10123-10132` — remote helper の初期化条件（primary cache、profile、pool）。
- `engine/src/program/generate.cpp:10139-10188` — auto / 複数 helper 時の候補追加、配置方式、順位分配。
- `engine/src/program/generate.cpp:10197-10208` — helper cache を開き、失敗時終了コード 1、成功時の stderr 出力。
- `engine/src/core/remote_experts.cpp:71-97` — helper device の可視性・primary との重複検査と free memory preflight。
- `engine/src/core/remote_experts.cpp:136-205` — slot と候補の検査、auto の 512 MiB 余裕を使った sizing、expert cache への fill / verify と失敗経路。
- `engine/src/core/remote_experts.cpp:207-238` — GPU scratch / stream と pinned host staging の割り当て。
- `engine/src/program/generate.cpp:23939-23948` — serve request ごとの helper 統計出力。

調査範囲は索引で `strata-engine` root parser とされる `engine/src/program/generate.cpp` およびそこから呼ばれる CUDA helper cache 実装である。GPU 実行は行っていないため、特定 GPU / driver で実際に確保できる数や実行時性能は確認していない。
