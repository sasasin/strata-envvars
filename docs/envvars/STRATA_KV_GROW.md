# `STRATA_KV_GROW`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。CUDA と SYCL の Strata 実装を確認した。外部ライブラリの動作は対象外。

## 役割

`--max-context` 全体分を最初に物理割り当てする代わりに、要求が使うセル数に応じて K/V の VRAM 使用量を増減させる機能を有効にする。K/V が必要とする領域は VMM の仮想アドレス範囲に確保され、コンテキストが伸びると expert cache の一部の物理チャンクを K/V に渡す。その分 cache の GPU 常駐 expert が減り、CPU 計算用に RAM にある expert が使われる。短い要求の後は K/V を縮小し、cache に枠を戻す処理もある。適用経路は `src/program/generate.cpp` と `sycl/src/program/generate.cpp` の生成・serve 処理。

## 値と判定

環境変数が未設定か空文字なら、CLI の `--kv-grow` / `--no-kv-grow` の結果を使う。CLI の既定値は OFF で、指定された toggle は引数解析中に `o.kv_grow` を設定するため、複数指定時は最後の指定が残る。空でない環境変数は CLI を上書きし、先頭文字が `0` なら OFF、それ以外なら ON と判定する。文字列全体や数値は parse しない。

| `STRATA_KV_GROW` | 実効要求値 |
|---|---|
| 未設定、または空文字 | CLI の設定（CLI もなければ OFF） |
| `0`, `0abc` | OFF |
| `1`, `true`, `false`, ` 0`, その他 `0` 以外で始まる非空文字列 | ON |

この環境変数は起動時の K/V セッション初期化ブロックで読み、その結果を `qsa_set_kv_elastic()` と `ExpertCache::set_vmm()` に渡す。同じプロセス内の各要求で `STRATA_KV_GROW` を読み直すコードはない。環境変数の変更を子プロセスへ伝える処理もこの設定経路にはない。根拠: `src/program/generate.cpp:4221-4238`, `1857-1858`; SYCL 対応箇所: `sycl/src/program/generate.cpp:3768-3785`, `1720-1721`。

## 有効になる条件

要求値が ON でも、次をすべて満たさなければ機能は有効にならない。

- GPU が1台である。
- `--kv-resident` による K/V streaming ではない（`o.kv_resident <= 0`）。
- expert profile が指定され、resident CPU experts モードではなく、expert cache が無効 (`o.expert_cache == 0`) でもない。
- remote expert cache を使わない。
- Strata が対象デバイスで VMM を利用できる。
- `--batch`、`--vram-elastic`、`--peer-device` を使わない。

この条件式が成立した場合だけ K/V の elastic mode と expert cache の VMM を有効にする。要求値が ON でも条件を満たさない場合は stderr に `strata generate: --kv-grow is off (one GPU, a profile, the whole K/V in VRAM, every expert in RAM, no --batch, --vram-elastic or --peer-device)` を出す。これは個々の不成立条件を特定するログではない。要求値が OFF の場合、この理由ログは出ない。根拠: `src/program/generate.cpp:4224-4238`; SYCL: `sycl/src/program/generate.cpp:3771-3785`。

## 実行時の詳細

起動時に `STRATA_KV_GROW_INIT` が正の `atoll` 値なら初期 K/V セル数に使われ、そうでなければ 16384 が渡される。この初期値用変数は本書の対象外だが、elastic K/V の初期マッピング量に関係する。実際の動的拡張を始める `kvg_start()` にも追加条件があり、expert cache に VMM range があり、device residency table・RAM 上の expert residency・profile source が用意され、cache の対象 slot 数が既定 floor の 128 slot より大きいことを確認する。その後、`STRATA_KV_GROW_FLOOR` に正の `atoll` 値があれば、拡張時に維持する slot 下限として floor を上書きする。

要求処理で必要セル数が現在の K/V より大きい場合、`kvg_ensure()` は必要数を `STRATA_KV_GROW_STEP`（正の `atoll` 値。既定 8192 cells）の倍数に切り上げ、`--max-context` で上限を設ける。未マップの K/V チャンクが足りない場合は cache の一部を空け、必要なら expert を cache 内のより低順位な枠へ移し、チャンクを K/V 側へ渡す。K/V を縮小する経路では cache に戻った枠を再利用する。これらの処理はすべて `kvg.on` のときだけ動く。

主要な呼び出しは、serve の cache 枠調整後、および generate の prompt 前・要求処理中に必要セル数を確保する箇所にある。拡張時には `strata: K/V grown to ...`、割当失敗時には `strata: the K/V could not grow to ...` を stderr に出す。増加処理はデバイス処理を静止させてから行う。CUDA/SYCL の VMM 実装は CUDA-driver VMM に依存し、HIP は `include/strata/core/vmm.hpp` の説明上サポート対象外。

根拠: `src/program/generate.cpp:6410-6433,6456-6485,6510-6528,7356,12441-12446,12482-12485`; 初期値設定は `src/program/generate.cpp:4236-4238`; SYCL の同等箇所は `sycl/src/program/generate.cpp:6065-6087,6111-6145,6202-6233,6940,11651-11657,11692-11696,11751-11755`; VMM の説明は `include/strata/core/vmm.hpp:1-5`。

## 文書との照合

`docs/DETAILS.md:261-264` は `--kv-grow` / `STRATA_KV_GROW=1` として紹介し、単一 GPU、profile、全 K/V を VRAM に置く構成、RAM に全 expert があること、および batch / vram-elastic / peer-device の除外を説明する。上記のコード条件と一致する。ただし docs の短い表記だけでは、空文字が CLI に戻ること、先頭文字判定で `false` も ON になること、他の適用条件（VMM availability・remote cache 等）は分からないため、ここでは実装に基づいて補足した。
