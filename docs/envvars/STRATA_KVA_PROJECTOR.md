# `STRATA_KVA_PROJECTOR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

この変数は projector ファイルのパスとして読み込まれ、`KvaConfig::projector` に保存されます。同時に KVA の mode を `Linear` にします。ただし、調査対象 commit の Strata 実装には projector ファイルを開く処理や、保存したパスを使って射影を計算する処理がありません。ヘッダーの説明も `linear` projector を「not implemented in this step」としています。したがって、この変数を設定しても projector の読み込みや線形射影は行われません。

## 値と判定

| 値 | 判定と結果 |
|---|---|
| 未設定 | パスを保存せず、この変数による mode 変更もしません。既定 mode は `Identity` です。 |
| 空文字 | `getenv()` は非 null ですが `*d != '\0'` 条件に合わず、未設定と同じ扱いです。 |
| 空でない文字列 | 内容を変換・検証せず、そのまま `projector` に保存して mode を `Linear` にします。パスの存在、形式、読み取り可否はこの箇所では確認しません。 |

数値 parse、値域、空白除去、大文字小文字変換はありません。環境変数の値をパス文字列として受け取ります。根拠: `include/strata/prefill/kva.hpp:93,173-176`。

## 有効になる条件

値が空でないと設定情報上は `Linear` mode になりますが、実際の KVA 処理は別の `STRATA_KVA` 設定と実行条件に依存します。`STRATA_KVA` が未設定・空・先頭文字が `0` の場合、KVA は off です。`STRATA_KVA` が有効でも、Metal build は state-only path がないため KVA を無効化します。また、layer split across GPUs、`--batch`、`--peer-device` はプロセス内の KVA を block します。CUDA/HIP build で、これらの block がなく、cold prompt・全 trunk・画像なし・DFlash2 tap なし・十分な長さ・測定対象 shape などの条件を満たす read で KVA が適用されます。これらは projector を有効化する条件ではなく、KVA の近似 read 自体の条件です。根拠: `include/strata/prefill/kva.hpp:43-49,104-133,152-156`; `src/program/generate.cpp:6257-6278`; `src/prefill/prefill.cpp:2947-2966`。

設定の上書き順は重要です。`STRATA_KVA_ORACLE` が非空なら先に mode を `Oracle` にし、次に `STRATA_KVA_PROJECTOR` が非空なら mode を `Linear` にします。最後に非空の `STRATA_KVA_MODE` があれば、値が完全一致で `oracle` または `linear` の場合にその mode を選び、それ以外の文字列なら `Identity` に戻します。このため、`STRATA_KVA_MODE` は projector 指定による mode 選択を上書きできます。空の `STRATA_KVA_MODE` は上書きしません。パス文字列は mode が後で上書きされても config 内に残りますが、現在の実行コードからは利用されません。根拠: `include/strata/prefill/kva.hpp:168-180`。

## 実行時の詳細

`kva_config()` は `static const KvaConfig` を初回呼び出し時に生成するため、環境値はプロセス内で一度だけ読み取られます。以後の環境変更は反映されません。テスト用の `kva_config_from_env()` は都度読み直しますが、本番の `Prefill::run_impl()` はキャッシュされた `kva_config()` を参照します。根拠: `include/strata/prefill/kva.hpp:149-195`; `src/prefill/prefill.cpp:2949`。

Prefill の層処理では、KVA の近似 layer を `kva_state_only` / `kva_moe_only` で分岐し、入力の置換を行う `kva_subst` は mode が `Oracle` の場合だけ true になります。`Linear` mode は projector を使いません。近似 layer は `STRATA_KVA_SKIP` に応じて state-only または moe-skip 経路で処理されます。したがって現状、非空の `STRATA_KVA_PROJECTOR` は mode 表示を `linear` に変えますが、近似 layer の実計算には projector を適用しません。根拠: `src/prefill/prefill.cpp:3619-3629,3689-3695`。

KVA が実行された場合は stderr に `strata prefill: KVA on: ... mode linear` と出ます。設定しても KVA 条件に合わなかった場合、明示的に `STRATA_KVA=1` で有効化されていれば `strata prefill: KVA configured but NOT applied: ...` と理由が出ます。`STRATA_KVA_PROJECTOR` 自体に関する警告、ファイル open、形式エラー、終了経路は実装されていません。根拠: `src/prefill/prefill.cpp:5820-5856`。

## 根拠

- `include/strata/prefill/kva.hpp:13-21` — `linear` projector は未実装との説明、環境設定を process 内で一度読む旨。
- `include/strata/prefill/kva.hpp:69-93,149-195` — config field、空でない値の取り込み、他 KVA 環境変数との設定順、cache。
- `src/program/generate.cpp:6257-6278` — backend と batch / GPU 条件による KVA block および関連ログ。
- `src/prefill/prefill.cpp:2947-2966,3619-3629,3689-3695,5820-5856` — KVA 適用条件、linear mode の実行経路、観測ログ。
- `docs/KVA.md:118,159-167,180-185` — `linear` は未実装との記載、および projector を置き換えるはずの mode に関する説明。現行実装でも projector path の消費箇所は確認できません。
